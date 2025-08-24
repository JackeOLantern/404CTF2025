#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <seccomp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/capability.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <sys/vfs.h>
#include <sys/wait.h>
#include <unistd.h>
#include <bits/local_lim.h>


#define ANSI_INFO 	       "\033[37m"
#define ANSI_INFO_VALUE    "\033[34m"
#define ANSI_SUCCESS       "\033[32;1m"
#define ANSI_SUCCESS_VALUE "\033[33;1m"
#define ANSI_ERROR         "\033[31;1m"
#define ANSI_ERROR_VALUE   "\033[35;1m"
#define ANSI_RESET         "\033[0m"

#define INFO(fmtstr, ...) printf(ANSI_INFO fmtstr ANSI_RESET "\n" __VA_OPT__(,) __VA_ARGS__)
#define INFVAL(fmtstr) ANSI_INFO_VALUE fmtstr ANSI_RESET ANSI_INFO
#define SUCCESS(fmtstr, ...) printf(ANSI_SUCCESS fmtstr ANSI_RESET "\n" __VA_OPT__(,) __VA_ARGS__)
#define SUCVAL(fmtstr) ANSI_SUCCESS_VALUE fmtstr ANSI_RESET ANSI_SUCCESS
#define ERROR(fmtstr, ...) printf(ANSI_ERROR fmtstr ANSI_RESET "\n" __VA_OPT__(,) __VA_ARGS__)
#define ERRVAL(fmtstr) ANSI_ERROR_VALUE fmtstr ANSI_RESET  ANSI_ERROR
#define PERROR(prefix) ERROR("%s: " ERRVAL("%s"), prefix, strerror(errno))
#define PANIC(prefix) { ERROR("%s: " ERRVAL("%s"), prefix, strerror(errno)); exit(-1); }

#define CGROUPS_PATH "/sys/fs/cgroup"
#define CGROUPS_RUNTIME_SLICE CGROUPS_PATH "/containers"
#define CGROUP2_SUPER_MAGIC 0x63677270

struct ContainerContext {
	char* baseDirectory;
	char* containerDirectory;
	char** containerCommand;
	char* containerCgroup;  // Populated when the cgroup is created
	char* containerHostname;
	pid_t hostPid;
};


struct ContainerContext defineIntendedContext(const int argc, char** argv) {
	if (argc < 4) {
		printf("Custom super-secure containers!\n\n");
		printf("Usage: %s <root dir> <container hostname> <executable>\n", argv[0]);
		printf("Example:\n");
		printf("\t%s /mnt/container-root container /bin/sh\n", argv[0]);
		exit(-1);
	}
	struct ContainerContext context;
	context.baseDirectory = argv[1];
	context.containerDirectory = argv[1];
	context.containerHostname = argv[2];
	context.containerCommand = argv + 3;
	context.hostPid = getpid();
	context.containerCgroup = NULL;
	return context;
}


void gatherHostInfo(const struct ContainerContext *context) {
	struct utsname hostInfo;
	if(uname(&hostInfo) != 0) {
		PANIC("Failed to get host uname");
	}
	SUCCESS(
			"Starting container on host" SUCVAL(" %s ")
			"running" SUCVAL(" %s v%s (%s)") ".",
			hostInfo.nodename,
			hostInfo.sysname,
			hostInfo.release,
			hostInfo.machine
	);
	INFO("Host process has PID" INFVAL(" %d") ".", context->hostPid);
}


void verifyCgroupV2Support() {
	INFO(
			"Making sure cgroup v2 filesystem is properly mounted at "
			INFVAL("%s") ".",
			CGROUPS_PATH
	);
	struct stat cgroupStats;
	if (stat(CGROUPS_PATH, &cgroupStats) != 0) {
		PANIC("Failed to assert cgroup v2 support");
	}
	if (!S_ISDIR(cgroupStats.st_mode)) {
		ERROR("Cgroup v2 mount point is not a directory");
		exit(-1);
	}
	struct statfs fsStats;
	if (statfs(CGROUPS_PATH, &fsStats) != 0) {
		PANIC("Failed to verify cgroup v2 mount point filesystem");
	}
	if (fsStats.f_type != CGROUP2_SUPER_MAGIC) {
		ERROR("Cgroup mount point is not a cgroup v2 filesystem.");
		exit(-1);
	}
}


void ensureRuntimeCgroupExists() {
	struct stat sliceStat;
	if (stat(CGROUPS_RUNTIME_SLICE, &sliceStat) != 0) {
		if (errno == ENOENT) {
			INFO(
					"Creating container runtime cgroup slice at " 
					INFVAL(CGROUPS_RUNTIME_SLICE) "."
			);
			if (mkdir(CGROUPS_RUNTIME_SLICE, S_IRUSR | S_IWUSR | S_IXUSR) != 0) {
				PANIC("Failed to create runtime cgroup slice");
			}
		} else {
			PANIC("Failed to verify container runtime cgroup slice.");
		}
	}
}


void createControlGroup(struct ContainerContext *context) {
 	// 9 chars for '/' + decimal pid + 0x00
	const size_t pathLen = strlen(CGROUPS_RUNTIME_SLICE) + sizeof("container-") + 9;
	context->containerCgroup = (char*) malloc(pathLen);
	snprintf(
			context->containerCgroup, pathLen,
			"%s/container-%d", CGROUPS_RUNTIME_SLICE, context->hostPid
	);
	INFO("Creating a control group at" INFVAL(" %s") "...", context->containerCgroup);
	if(mkdir(context->containerCgroup, S_IRUSR | S_IWUSR | S_IXUSR) != 0) {
		PANIC("Failed to create cgroup");
	}
}


void addProcessToCgroup(const char *cgroup, const pid_t pid) {
	char *path = malloc(strlen(cgroup) + sizeof("cgroup.procs") + 2);
	strcpy(path, cgroup);
	strcat(path, "/");
	strcat(path, "cgroup.procs");
	INFO( "Adding process" INFVAL(" %d ") "to cgroup" INFVAL(" %s") ".", pid, path);
	const int fd = open(path, O_WRONLY);
	if (fd == -1) {
		PANIC("Failed to open cgroup process file");
	}
	char pidstr[16];
	snprintf(pidstr, sizeof(pidstr), "%d", pid);
	if (write(fd, pidstr, strlen(pidstr)) == -1) {
		close(fd);
		PANIC("Failed to write to cgroup process file");
	}
	free(path);
	close(fd);
}


void enableCgroupController(const char *cgroup, const char *controller) {
	char *path = malloc(strlen(cgroup) + sizeof("cgroup.subtree_control") + 2);
	strcpy(path, cgroup);
	strcat(path, "/");
	strcat(path, "cgroup.subtree_control");
	INFO( "Enabling" INFVAL(" %s ") "cgroup controller in" INFVAL(" %s") ".", controller, path);
	int fd = open(path, O_WRONLY);
	if (fd == -1) {
		PANIC("Failed to open cgroup control file");
	}
	size_t strLen = strlen(controller) + 2;
	char *controllerString = (char *) malloc(strLen + 1);
	snprintf(controllerString, strLen + 1, "+%s\n", controller);
	if (write(fd, controllerString, strLen) == -1) {
		free(controllerString);
		close(fd);
		PANIC("Failed to write to cgroup control file");
	}
	free(path);
	free(controllerString);
	close(fd);
}


void setCpuLimit(const char *cgroup, const int usePercent) {
	char *path = malloc(strlen(cgroup) + sizeof("cpu.max") + 2);
	strcpy(path, cgroup);
	strcat(path, "/");
	strcat(path, "cpu.max");
	INFO("Limiting CPU usage to" INFVAL(" %d%% ") "in " INFVAL(" %s") ".", usePercent, path);
	if (usePercent <= 0 || usePercent > 100) {
		ERROR("Invalid CPU usage :" ERRVAL(" %d%%") ".", usePercent);
		exit(-1);
	}
	const int fd = open(path, O_WRONLY);
	if (fd == -1) {
		PANIC("Failed to open cgroup cpu limit file");
	}
	char limitStr[32];
	snprintf(limitStr, sizeof(limitStr), "%d %d", usePercent * 1000, 100000);
	if (write(fd, limitStr, strlen(limitStr)) == -1) {
		close(fd);
		PANIC("Failed to write to cgroup cpu limit file");
	}
	free(path);
	close(fd);
}


void setMemoryLimit(const char *cgroup, int memLimitMB) {
	char *path = malloc(strlen(cgroup) + sizeof("memory.max") + 2);
	strcpy(path, cgroup);
	strcat(path, "/");
	strcat(path, "memory.max");
	INFO("Limiting memory usage to" INFVAL(" %dMiB ") "in " INFVAL(" %s") ".", memLimitMB, path);
	if (memLimitMB <= 0) {
		ERROR("Invalid memory limit usage:" ERRVAL(" %dMiB") ".", memLimitMB);
		exit(-1);
	}
	const int fd = open(path, O_WRONLY);
	if (fd == -1) {
		PANIC("Failed to open cgroup memory limit file");
	}
	char limitStr[1024];
	snprintf(limitStr, sizeof(limitStr), "%dM", memLimitMB);
	if (write(fd, limitStr, strlen(limitStr)) == -1) {
		close(fd);
		PANIC("Failed to write to cgroup memory limit file");
	}
	free(path);
	close(fd);
}


void setPidsLimit(const char *cgroup, const int maxProcessCount) {
	char *path = malloc(strlen(cgroup) + sizeof("pids.max") + 2);
	strcpy(path, cgroup);
	strcat(path, "/");
	strcat(path, "pids.max");
	INFO("Limiting processe count to" INFVAL(" %d pids ") "in " INFVAL(" %s") ".", maxProcessCount, path);
	if (maxProcessCount <= 0) {
		ERROR("Invalid pids limit usage:" ERRVAL(" %d") ".", maxProcessCount);
		exit(-1);
	}
	const int fd = open(path, O_WRONLY);
	if (fd == -1) {
		PANIC("Failed to open cgroup pids limit file");
	}
	char limitStr[1024];
	snprintf(limitStr, sizeof(limitStr), "%d", maxProcessCount);
	if (write(fd, limitStr, strlen(limitStr)) == -1) {
		close(fd);
		PANIC("Failed to write to cgroup pids limit file");
	}
	free(path);
	close(fd);
}


void enterControlGroup(struct ContainerContext *context) {
	verifyCgroupV2Support();
	ensureRuntimeCgroupExists();
	createControlGroup(context);
	addProcessToCgroup(context->containerCgroup, context->hostPid);
	enableCgroupController(CGROUPS_RUNTIME_SLICE, "cpu");
	enableCgroupController(CGROUPS_RUNTIME_SLICE, "memory");
	enableCgroupController(CGROUPS_RUNTIME_SLICE, "pids");
	setCpuLimit(context->containerCgroup, 75);
	setMemoryLimit(context->containerCgroup, 50);
	setPidsLimit(context->containerCgroup, 10);
	SUCCESS("Enforced resource limits in container.");
}


void changeRoot(const struct ContainerContext *context) {
	INFO("Changing working directory to" INFVAL(" %s") ".", context->containerDirectory);
	if (chdir(context->baseDirectory) != 0) {
		PANIC("Failed to change directory  to new root");
	}
	INFO("Changing root directory to" INFVAL(" ./") ".");
	if (chroot("./") != 0) {
		PANIC("Failed to chroot");
	}
	char* cwd = getcwd(NULL, 0);
	if (cwd == NULL) {
		PERROR("Failed to get current working directory");
	} else {
		SUCCESS("Current working directory is now" SUCVAL(" %s") ".", cwd);
		free(cwd);
	}
}


void enterNamespaces() {
	const int flags =
	    CLONE_NEWCGROUP
		| CLONE_NEWIPC
		| CLONE_NEWNET
		| CLONE_NEWNS
		| CLONE_NEWPID
		| CLONE_NEWUTS;
	INFO(
			"Setting up namespaces for "
			INFVAL("control groups") ", "
			INFVAL("inter-process communications") ", "
			INFVAL("networking") ", "
			INFVAL("mounts") ", "
			INFVAL("processes") " and "
			INFVAL("hostnames") "."
	);
	if (unshare(flags) != 0) {
		PANIC("Failed to unshare");
	}
	INFO("Forking to enter PID namespace.");
	const pid_t newPid = fork();
	if (newPid == 0) {
		SUCCESS("Entered container namespace, now running as pid " SUCVAL("%d") ".", getpid());
	} else if (newPid == -1) {
		PANIC("Fork failed");
	} else {
		INFO("Container init has pid" INFVAL(" %d ") "from the outside.", newPid);
		wait(NULL);
		umount("/proc");
		umount("/tmp");
		exit(0);
	}
}
	

void execPayload(const struct ContainerContext *context) {
	SUCCESS(
			"Done setting-up container. "
			"Now executing" SUCVAL(" %s ") "as container init with execve...",
			context->containerCommand[0]
	);
	fflush(stdout);  // We need to flush anything in the buffer to avoid missing lines
	execve(context->containerCommand[0], context->containerCommand, NULL);
	PANIC("Failed to execve");
}


void mountChecked(const char *source, const char *target, const char *fsType, const unsigned long flags, const void *data) {
	INFO("Mounting" INFVAL(" %s ") "at" INFVAL(" %s") ".", source, target);
	if (mount(source, target, fsType, flags, data) != 0) {
		PANIC("Mount failed");
	}
}


void setupContainerMounts(struct ContainerContext *context) {
	mountChecked("proc", "/proc", "proc", 0, NULL);
	mountChecked("tmpfs", "/tmp", "tmpfs", 0, NULL);
	SUCCESS("Mounted " SUCVAL("procfs") " and " SUCVAL("tmpfs") " inside the container.");
}


void setContainerHostname(const struct ContainerContext *context) {
	INFO("Writing " INFVAL("%s") " to " INFVAL("/etc/hostname"), context->containerHostname);
	const int fd = open("/etc/hostname", O_CREAT | O_WRONLY);
	if (fd == -1) {
		PANIC("Failed to open hostname file");
	}
	if (write(fd, context->containerHostname, strlen(context->containerHostname)) == -1) {
		close(fd);
		PANIC("Failed to write to hostname file");
	}
	close(fd);
	INFO("Changing namespace hostname to " INFVAL("%s") ".", context->containerHostname);
	if (sethostname(context->containerHostname, strnlen(context->containerHostname, HOST_NAME_MAX)) != 0) {
		PANIC("Failed to set hostname")
	}
	char newHostname[HOST_NAME_MAX + 1];
	if (gethostname(newHostname, HOST_NAME_MAX) != 0) {
		PANIC("Failed to get new hostname");
	}
	SUCCESS("Renamed container, hostname is now " SUCVAL("%s") ".", newHostname);
}


void dropCapabilities(const struct ContainerContext *context) {
	const cap_value_t capabilities[] = {
		CAP_AUDIT_CONTROL,
		CAP_AUDIT_READ,
		CAP_AUDIT_WRITE,
		CAP_BLOCK_SUSPEND,
		CAP_BPF,
		CAP_CHECKPOINT_RESTORE,
		CAP_CHOWN,
		CAP_DAC_OVERRIDE,
		CAP_DAC_READ_SEARCH,
		CAP_FOWNER,
		CAP_FSETID,
		CAP_IPC_LOCK,
		CAP_IPC_OWNER,
		CAP_KILL,
		CAP_LEASE,
		CAP_LINUX_IMMUTABLE,
		CAP_MAC_ADMIN,
		CAP_MAC_OVERRIDE,
		CAP_MKNOD,
		CAP_NET_ADMIN,
		CAP_NET_RAW,
		CAP_PERFMON,
		CAP_SETFCAP,
		CAP_SETPCAP,
		CAP_SYS_ADMIN,
		CAP_SYS_BOOT,
		CAP_SYS_MODULE,
		CAP_SYS_NICE,
		CAP_SYS_PACCT,
		CAP_SYS_PTRACE,
		CAP_SYS_RAWIO,
		CAP_SYS_RESOURCE,
		CAP_SYS_TIME,
		CAP_SYS_TTY_CONFIG,
		CAP_SYSLOG,
		CAP_WAKE_ALARM,
	};
	const int capCount = sizeof(capabilities) / sizeof(cap_value_t);
	printf(ANSI_INFO "Dropping bounding capabilities ");
	for (int i = 0; i < capCount; i++) {
		const char *terminal = i == capCount - 1 ? ".\n" : i == capCount - 2 ? " and " : ", ";
		const cap_value_t capability = capabilities[i];
		printf(ANSI_INFO_VALUE "%s" ANSI_INFO "%s", cap_to_name(capability), terminal);
		if (cap_drop_bound(capability) != 0) {
			printf(SUCVAL("\n") ANSI_RESET);
			PANIC("Failed to drop bounding capability")
		}
	}
	INFO("Dropping the same inheritable capabilities.");
	cap_t capabilitySet = cap_get_proc();
	if (capabilitySet == NULL) {
		PANIC("Failed to get capabilities");
	}
	if (cap_set_flag(capabilitySet, CAP_INHERITABLE, capCount, capabilities, CAP_CLEAR) != 0) {
		PANIC("Failed to set capability set flags");
	}
	if (cap_set_proc(capabilitySet) != 0) {
		PANIC("Failed to set inheritable capabilities")
	}
	cap_free(capabilitySet);
	SUCCESS("Dropped container capabilities.");
}


#define SECCOMP_ALLOW_SYSCALL_GENERIC(filter, syscall, separator) \
	if (seccomp_rule_add(filter, SCMP_ACT_ALLOW, SCMP_SYS(syscall), 0) != 0) {\
		PANIC("Failed to allow syscall"); \
	} else {\
		printf(ANSI_INFO_VALUE #syscall ANSI_INFO separator ANSI_RESET);\
	}
#define SECCOMP_ALLOW_SYSCALL(filter, syscall) SECCOMP_ALLOW_SYSCALL_GENERIC(filter, syscall, ", ")
#define SECCOMP_ALLOW_SYSCALL_LAST(filter, syscall) SECCOMP_ALLOW_SYSCALL_GENERIC(filter, syscall, ".\n")

void setupSeccomp() {
	printf(ANSI_INFO "Setting up seccomp, allowing the following syscalls: ");
	scmp_filter_ctx filter = seccomp_init(SCMP_ACT_ERRNO(EPERM));
	if (filter == NULL) {
		PANIC("Failed to create seccomp filter");
	}
	SECCOMP_ALLOW_SYSCALL(filter, accept);
	SECCOMP_ALLOW_SYSCALL(filter, accept4);
	SECCOMP_ALLOW_SYSCALL(filter, access);
	SECCOMP_ALLOW_SYSCALL(filter, adjtimex);
	SECCOMP_ALLOW_SYSCALL(filter, alarm);
	SECCOMP_ALLOW_SYSCALL(filter, arch_prctl);
	SECCOMP_ALLOW_SYSCALL(filter, bind);
	SECCOMP_ALLOW_SYSCALL(filter, brk);
	SECCOMP_ALLOW_SYSCALL(filter, capget);
	SECCOMP_ALLOW_SYSCALL(filter, capset);
	SECCOMP_ALLOW_SYSCALL(filter, chdir);
	SECCOMP_ALLOW_SYSCALL(filter, chmod);
	SECCOMP_ALLOW_SYSCALL(filter, chown);
	SECCOMP_ALLOW_SYSCALL(filter, chown32);
	SECCOMP_ALLOW_SYSCALL(filter, chroot);
	SECCOMP_ALLOW_SYSCALL(filter, clock_adjtime);
	SECCOMP_ALLOW_SYSCALL(filter, clock_adjtime64);
	SECCOMP_ALLOW_SYSCALL(filter, clock_getres);
	SECCOMP_ALLOW_SYSCALL(filter, clock_gettime);
	SECCOMP_ALLOW_SYSCALL(filter, clock_gettime64);
	SECCOMP_ALLOW_SYSCALL(filter, clock_nanosleep);
	SECCOMP_ALLOW_SYSCALL(filter, clock_nanosleep_time64);
	SECCOMP_ALLOW_SYSCALL(filter, clone);
	SECCOMP_ALLOW_SYSCALL(filter, close);
	SECCOMP_ALLOW_SYSCALL(filter, close_range);
	SECCOMP_ALLOW_SYSCALL(filter, connect);
	SECCOMP_ALLOW_SYSCALL(filter, copy_file_range);
	SECCOMP_ALLOW_SYSCALL(filter, creat);
	SECCOMP_ALLOW_SYSCALL(filter, dup);
	SECCOMP_ALLOW_SYSCALL(filter, dup2);
	SECCOMP_ALLOW_SYSCALL(filter, dup3);
	SECCOMP_ALLOW_SYSCALL(filter, epoll_create);
	SECCOMP_ALLOW_SYSCALL(filter, epoll_create1);
	SECCOMP_ALLOW_SYSCALL(filter, epoll_ctl);
	SECCOMP_ALLOW_SYSCALL(filter, epoll_ctl_old);
	SECCOMP_ALLOW_SYSCALL(filter, epoll_pwait);
	SECCOMP_ALLOW_SYSCALL(filter, epoll_pwait2);
	SECCOMP_ALLOW_SYSCALL(filter, epoll_wait);
	SECCOMP_ALLOW_SYSCALL(filter, epoll_wait_old);
	SECCOMP_ALLOW_SYSCALL(filter, eventfd);
	SECCOMP_ALLOW_SYSCALL(filter, eventfd2);
	SECCOMP_ALLOW_SYSCALL(filter, execve);
	SECCOMP_ALLOW_SYSCALL(filter, execveat);
	SECCOMP_ALLOW_SYSCALL(filter, exit);
	SECCOMP_ALLOW_SYSCALL(filter, exit_group);
	SECCOMP_ALLOW_SYSCALL(filter, faccessat);
	SECCOMP_ALLOW_SYSCALL(filter, fadvise64);
	SECCOMP_ALLOW_SYSCALL(filter, fadvise64_64);
	SECCOMP_ALLOW_SYSCALL(filter, fallocate);
	SECCOMP_ALLOW_SYSCALL(filter, fanotify_mark);
	SECCOMP_ALLOW_SYSCALL(filter, fchdir);
	SECCOMP_ALLOW_SYSCALL(filter, fchmod);
	SECCOMP_ALLOW_SYSCALL(filter, fchmodat);
	SECCOMP_ALLOW_SYSCALL(filter, fchown);
	SECCOMP_ALLOW_SYSCALL(filter, fchown32);
	SECCOMP_ALLOW_SYSCALL(filter, fchownat);
	SECCOMP_ALLOW_SYSCALL(filter, fcntl);
	SECCOMP_ALLOW_SYSCALL(filter, fcntl64);
	SECCOMP_ALLOW_SYSCALL(filter, fdatasync);
	SECCOMP_ALLOW_SYSCALL(filter, fgetxattr);
	SECCOMP_ALLOW_SYSCALL(filter, flistxattr);
	SECCOMP_ALLOW_SYSCALL(filter, flock);
	SECCOMP_ALLOW_SYSCALL(filter, fork);
	SECCOMP_ALLOW_SYSCALL(filter, fremovexattr);
	SECCOMP_ALLOW_SYSCALL(filter, fsetxattr);
	SECCOMP_ALLOW_SYSCALL(filter, fstat);
	SECCOMP_ALLOW_SYSCALL(filter, fstat64);
	SECCOMP_ALLOW_SYSCALL(filter, fstatat64);
	SECCOMP_ALLOW_SYSCALL(filter, fstatfs);
	SECCOMP_ALLOW_SYSCALL(filter, fstatfs64);
	SECCOMP_ALLOW_SYSCALL(filter, fsync);
	SECCOMP_ALLOW_SYSCALL(filter, ftruncate);
	SECCOMP_ALLOW_SYSCALL(filter, ftruncate64);
	SECCOMP_ALLOW_SYSCALL(filter, futex);
	SECCOMP_ALLOW_SYSCALL(filter, futex_time64);
	SECCOMP_ALLOW_SYSCALL(filter, futex_waitv);
	SECCOMP_ALLOW_SYSCALL(filter, futimesat);
	SECCOMP_ALLOW_SYSCALL(filter, getcpu);
	SECCOMP_ALLOW_SYSCALL(filter, getcwd);
	SECCOMP_ALLOW_SYSCALL(filter, getdents);
	SECCOMP_ALLOW_SYSCALL(filter, getdents64);
	SECCOMP_ALLOW_SYSCALL(filter, getegid);
	SECCOMP_ALLOW_SYSCALL(filter, getegid32);
	SECCOMP_ALLOW_SYSCALL(filter, geteuid);
	SECCOMP_ALLOW_SYSCALL(filter, geteuid32);
	SECCOMP_ALLOW_SYSCALL(filter, getgid);
	SECCOMP_ALLOW_SYSCALL(filter, getgid32);
	SECCOMP_ALLOW_SYSCALL(filter, getgroups);
	SECCOMP_ALLOW_SYSCALL(filter, getgroups32);
	SECCOMP_ALLOW_SYSCALL(filter, getitimer);
	SECCOMP_ALLOW_SYSCALL(filter, getpeername);
	SECCOMP_ALLOW_SYSCALL(filter, getpgid);
	SECCOMP_ALLOW_SYSCALL(filter, getpgrp);
	SECCOMP_ALLOW_SYSCALL(filter, getpid);
	SECCOMP_ALLOW_SYSCALL(filter, getppid);
	SECCOMP_ALLOW_SYSCALL(filter, getpriority);
	SECCOMP_ALLOW_SYSCALL(filter, getrandom);
	SECCOMP_ALLOW_SYSCALL(filter, getresgid);
	SECCOMP_ALLOW_SYSCALL(filter, getresgid32);
	SECCOMP_ALLOW_SYSCALL(filter, getresuid);
	SECCOMP_ALLOW_SYSCALL(filter, getresuid32);
	SECCOMP_ALLOW_SYSCALL(filter, getrlimit);
	SECCOMP_ALLOW_SYSCALL(filter, get_robust_list);
	SECCOMP_ALLOW_SYSCALL(filter, getrusage);
	SECCOMP_ALLOW_SYSCALL(filter, getsid);
	SECCOMP_ALLOW_SYSCALL(filter, getsockname);
	SECCOMP_ALLOW_SYSCALL(filter, getsockopt);
	SECCOMP_ALLOW_SYSCALL(filter, get_thread_area);
	SECCOMP_ALLOW_SYSCALL(filter, gettid);
	SECCOMP_ALLOW_SYSCALL(filter, gettimeofday);
	SECCOMP_ALLOW_SYSCALL(filter, getuid);
	SECCOMP_ALLOW_SYSCALL(filter, getuid32);
	SECCOMP_ALLOW_SYSCALL(filter, getxattr);
	SECCOMP_ALLOW_SYSCALL(filter, inotify_add_watch);
	SECCOMP_ALLOW_SYSCALL(filter, inotify_init);
	SECCOMP_ALLOW_SYSCALL(filter, inotify_init1);
	SECCOMP_ALLOW_SYSCALL(filter, inotify_rm_watch);
	SECCOMP_ALLOW_SYSCALL(filter, io_cancel);
	SECCOMP_ALLOW_SYSCALL(filter, ioctl);
	SECCOMP_ALLOW_SYSCALL(filter, io_destroy);
	SECCOMP_ALLOW_SYSCALL(filter, io_getevents);
	SECCOMP_ALLOW_SYSCALL(filter, io_pgetevents);
	SECCOMP_ALLOW_SYSCALL(filter, io_pgetevents_time64);
	SECCOMP_ALLOW_SYSCALL(filter, ioprio_get);
	SECCOMP_ALLOW_SYSCALL(filter, ioprio_set);
	SECCOMP_ALLOW_SYSCALL(filter, io_setup);
	SECCOMP_ALLOW_SYSCALL(filter, io_submit);
	SECCOMP_ALLOW_SYSCALL(filter, ipc);
	SECCOMP_ALLOW_SYSCALL(filter, kexec_file_load);
	SECCOMP_ALLOW_SYSCALL(filter, kexec_load);
	SECCOMP_ALLOW_SYSCALL(filter, kill);
	SECCOMP_ALLOW_SYSCALL(filter, landlock_add_rule);
	SECCOMP_ALLOW_SYSCALL(filter, landlock_create_ruleset);
	SECCOMP_ALLOW_SYSCALL(filter, landlock_restrict_self);
	SECCOMP_ALLOW_SYSCALL(filter, lchown);
	SECCOMP_ALLOW_SYSCALL(filter, lchown32);
	SECCOMP_ALLOW_SYSCALL(filter, lgetxattr);
	SECCOMP_ALLOW_SYSCALL(filter, link);
	SECCOMP_ALLOW_SYSCALL(filter, linkat);
	SECCOMP_ALLOW_SYSCALL(filter, listen);
	SECCOMP_ALLOW_SYSCALL(filter, listxattr);
	SECCOMP_ALLOW_SYSCALL(filter, llistxattr);
	SECCOMP_ALLOW_SYSCALL(filter, _llseek);
	SECCOMP_ALLOW_SYSCALL(filter, lremovexattr);
	SECCOMP_ALLOW_SYSCALL(filter, lseek);
	SECCOMP_ALLOW_SYSCALL(filter, lsetxattr);
	SECCOMP_ALLOW_SYSCALL(filter, lstat);
	SECCOMP_ALLOW_SYSCALL(filter, lstat64);
	SECCOMP_ALLOW_SYSCALL(filter, madvise);
	SECCOMP_ALLOW_SYSCALL(filter, map_shadow_stack);
	SECCOMP_ALLOW_SYSCALL(filter, membarrier);
	SECCOMP_ALLOW_SYSCALL(filter, memfd_create);
	SECCOMP_ALLOW_SYSCALL(filter, mincore);
	SECCOMP_ALLOW_SYSCALL(filter, mkdir);
	SECCOMP_ALLOW_SYSCALL(filter, mkdirat);
	SECCOMP_ALLOW_SYSCALL(filter, mlock);
	SECCOMP_ALLOW_SYSCALL(filter, mlock2);
	SECCOMP_ALLOW_SYSCALL(filter, mlockall);
	SECCOMP_ALLOW_SYSCALL(filter, mmap);
	SECCOMP_ALLOW_SYSCALL(filter, mmap2);
	SECCOMP_ALLOW_SYSCALL(filter, modify_ldt);
	SECCOMP_ALLOW_SYSCALL(filter, mprotect);
	SECCOMP_ALLOW_SYSCALL(filter, mq_getsetattr);
	SECCOMP_ALLOW_SYSCALL(filter, mq_notify);
	SECCOMP_ALLOW_SYSCALL(filter, mq_open);
	SECCOMP_ALLOW_SYSCALL(filter, mq_timedreceive);
	SECCOMP_ALLOW_SYSCALL(filter, mq_timedsend);
	SECCOMP_ALLOW_SYSCALL(filter, mq_unlink);
	SECCOMP_ALLOW_SYSCALL(filter, mremap);
	SECCOMP_ALLOW_SYSCALL(filter, msgctl);
	SECCOMP_ALLOW_SYSCALL(filter, msgget);
	SECCOMP_ALLOW_SYSCALL(filter, msgrcv);
	SECCOMP_ALLOW_SYSCALL(filter, msgsnd);
	SECCOMP_ALLOW_SYSCALL(filter, msync);
	SECCOMP_ALLOW_SYSCALL(filter, munlock);
	SECCOMP_ALLOW_SYSCALL(filter, munlockall);
	SECCOMP_ALLOW_SYSCALL(filter, munmap);
	SECCOMP_ALLOW_SYSCALL(filter, nanosleep);
	SECCOMP_ALLOW_SYSCALL(filter, newfstatat);
	SECCOMP_ALLOW_SYSCALL(filter, _newselect);
	SECCOMP_ALLOW_SYSCALL(filter, open);
	SECCOMP_ALLOW_SYSCALL(filter, openat);
	SECCOMP_ALLOW_SYSCALL(filter, open_by_handle_at);
	SECCOMP_ALLOW_SYSCALL(filter, pause);
	SECCOMP_ALLOW_SYSCALL(filter, pipe);
	SECCOMP_ALLOW_SYSCALL(filter, pipe2);
	SECCOMP_ALLOW_SYSCALL(filter, pivot_root);
	SECCOMP_ALLOW_SYSCALL(filter, poll);
	SECCOMP_ALLOW_SYSCALL(filter, ppoll);
	SECCOMP_ALLOW_SYSCALL(filter, prctl);
	SECCOMP_ALLOW_SYSCALL(filter, pread64);
	SECCOMP_ALLOW_SYSCALL(filter, preadv);
	SECCOMP_ALLOW_SYSCALL(filter, prlimit64);
	SECCOMP_ALLOW_SYSCALL(filter, pselect6);
	SECCOMP_ALLOW_SYSCALL(filter, pwrite64);
	SECCOMP_ALLOW_SYSCALL(filter, pwritev);
	SECCOMP_ALLOW_SYSCALL(filter, read);
	SECCOMP_ALLOW_SYSCALL(filter, readahead);
	SECCOMP_ALLOW_SYSCALL(filter, readlink);
	SECCOMP_ALLOW_SYSCALL(filter, readlinkat);
	SECCOMP_ALLOW_SYSCALL(filter, readv);
	SECCOMP_ALLOW_SYSCALL(filter, recv);
	SECCOMP_ALLOW_SYSCALL(filter, recvfrom);
	SECCOMP_ALLOW_SYSCALL(filter, recvmmsg);
	SECCOMP_ALLOW_SYSCALL(filter, recvmsg);
	SECCOMP_ALLOW_SYSCALL(filter, remap_file_pages);
	SECCOMP_ALLOW_SYSCALL(filter, removexattr);
	SECCOMP_ALLOW_SYSCALL(filter, rename);
	SECCOMP_ALLOW_SYSCALL(filter, renameat);
	SECCOMP_ALLOW_SYSCALL(filter, renameat2);
	SECCOMP_ALLOW_SYSCALL(filter, restart_syscall);
	SECCOMP_ALLOW_SYSCALL(filter, rmdir);
	SECCOMP_ALLOW_SYSCALL(filter, rt_sigaction);
	SECCOMP_ALLOW_SYSCALL(filter, rt_sigpending);
	SECCOMP_ALLOW_SYSCALL(filter, rt_sigprocmask);
	SECCOMP_ALLOW_SYSCALL(filter, rt_sigqueueinfo);
	SECCOMP_ALLOW_SYSCALL(filter, rt_sigreturn);
	SECCOMP_ALLOW_SYSCALL(filter, rt_sigsuspend);
	SECCOMP_ALLOW_SYSCALL(filter, rt_sigtimedwait);
	SECCOMP_ALLOW_SYSCALL(filter, rt_tgsigqueueinfo);
	SECCOMP_ALLOW_SYSCALL(filter, sched_getaffinity);
	SECCOMP_ALLOW_SYSCALL(filter, sched_getattr);
	SECCOMP_ALLOW_SYSCALL(filter, sched_getparam);
	SECCOMP_ALLOW_SYSCALL(filter, sched_get_priority_max);
	SECCOMP_ALLOW_SYSCALL(filter, sched_get_priority_min);
	SECCOMP_ALLOW_SYSCALL(filter, sched_getscheduler);
	SECCOMP_ALLOW_SYSCALL(filter, sched_rr_get_interval);
	SECCOMP_ALLOW_SYSCALL(filter, sched_setaffinity);
	SECCOMP_ALLOW_SYSCALL(filter, sched_setattr);
	SECCOMP_ALLOW_SYSCALL(filter, sched_setparam);
	SECCOMP_ALLOW_SYSCALL(filter, sched_setscheduler);
	SECCOMP_ALLOW_SYSCALL(filter, sched_yield);
	SECCOMP_ALLOW_SYSCALL(filter, seccomp);
	SECCOMP_ALLOW_SYSCALL(filter, select);
	SECCOMP_ALLOW_SYSCALL(filter, semctl);
	SECCOMP_ALLOW_SYSCALL(filter, semget);
	SECCOMP_ALLOW_SYSCALL(filter, semop);
	SECCOMP_ALLOW_SYSCALL(filter, semtimedop);
	SECCOMP_ALLOW_SYSCALL(filter, send);
	SECCOMP_ALLOW_SYSCALL(filter, sendfile);
	SECCOMP_ALLOW_SYSCALL(filter, sendfile64);
	SECCOMP_ALLOW_SYSCALL(filter, sendmmsg);
	SECCOMP_ALLOW_SYSCALL(filter, sendmsg);
	SECCOMP_ALLOW_SYSCALL(filter, sendto);
	SECCOMP_ALLOW_SYSCALL(filter, setfsgid);
	SECCOMP_ALLOW_SYSCALL(filter, setfsgid32);
	SECCOMP_ALLOW_SYSCALL(filter, setfsuid);
	SECCOMP_ALLOW_SYSCALL(filter, setfsuid32);
	SECCOMP_ALLOW_SYSCALL(filter, setgid);
	SECCOMP_ALLOW_SYSCALL(filter, setgid32);
	SECCOMP_ALLOW_SYSCALL(filter, setgroups);
	SECCOMP_ALLOW_SYSCALL(filter, setgroups32);
	SECCOMP_ALLOW_SYSCALL(filter, setitimer);
	SECCOMP_ALLOW_SYSCALL(filter, setpgid);
	SECCOMP_ALLOW_SYSCALL(filter, setpriority);
	SECCOMP_ALLOW_SYSCALL(filter, setregid);
	SECCOMP_ALLOW_SYSCALL(filter, setregid32);
	SECCOMP_ALLOW_SYSCALL(filter, setresgid);
	SECCOMP_ALLOW_SYSCALL(filter, setresgid32);
	SECCOMP_ALLOW_SYSCALL(filter, setresuid);
	SECCOMP_ALLOW_SYSCALL(filter, setresuid32);
	SECCOMP_ALLOW_SYSCALL(filter, setreuid);
	SECCOMP_ALLOW_SYSCALL(filter, setreuid32);
	SECCOMP_ALLOW_SYSCALL(filter, setrlimit);
	SECCOMP_ALLOW_SYSCALL(filter, set_robust_list);
	SECCOMP_ALLOW_SYSCALL(filter, setsid);
	SECCOMP_ALLOW_SYSCALL(filter, setsockopt);
	SECCOMP_ALLOW_SYSCALL(filter, set_thread_area);
	SECCOMP_ALLOW_SYSCALL(filter, set_tid_address);
	SECCOMP_ALLOW_SYSCALL(filter, setuid);
	SECCOMP_ALLOW_SYSCALL(filter, setuid32);
	SECCOMP_ALLOW_SYSCALL(filter, setxattr);
	SECCOMP_ALLOW_SYSCALL(filter, shmat);
	SECCOMP_ALLOW_SYSCALL(filter, shmctl);
	SECCOMP_ALLOW_SYSCALL(filter, shmdt);
	SECCOMP_ALLOW_SYSCALL(filter, shmget);
	SECCOMP_ALLOW_SYSCALL(filter, shutdown);
	SECCOMP_ALLOW_SYSCALL(filter, sigaltstack);
	SECCOMP_ALLOW_SYSCALL(filter, signalfd);
	SECCOMP_ALLOW_SYSCALL(filter, signalfd4);
	SECCOMP_ALLOW_SYSCALL(filter, sigreturn);
	SECCOMP_ALLOW_SYSCALL(filter, socket);
	SECCOMP_ALLOW_SYSCALL(filter, socketcall);
	SECCOMP_ALLOW_SYSCALL(filter, socketpair);
	SECCOMP_ALLOW_SYSCALL(filter, splice);
	SECCOMP_ALLOW_SYSCALL(filter, stat);
	SECCOMP_ALLOW_SYSCALL(filter, stat64);
	SECCOMP_ALLOW_SYSCALL(filter, statfs);
	SECCOMP_ALLOW_SYSCALL(filter, statfs64);
	SECCOMP_ALLOW_SYSCALL(filter, statx);
	SECCOMP_ALLOW_SYSCALL(filter, symlink);
	SECCOMP_ALLOW_SYSCALL(filter, symlinkat);
	SECCOMP_ALLOW_SYSCALL(filter, sync);
	SECCOMP_ALLOW_SYSCALL(filter, sync_file_range);
	SECCOMP_ALLOW_SYSCALL(filter, syncfs);
	SECCOMP_ALLOW_SYSCALL(filter, sysinfo);
	SECCOMP_ALLOW_SYSCALL(filter, syslog);
	SECCOMP_ALLOW_SYSCALL(filter, tee);
	SECCOMP_ALLOW_SYSCALL(filter, tgkill);
	SECCOMP_ALLOW_SYSCALL(filter, time);
	SECCOMP_ALLOW_SYSCALL(filter, timer_create);
	SECCOMP_ALLOW_SYSCALL(filter, timer_delete);
	SECCOMP_ALLOW_SYSCALL(filter, timerfd_create);
	SECCOMP_ALLOW_SYSCALL(filter, timerfd_gettime);
	SECCOMP_ALLOW_SYSCALL(filter, timerfd_settime);
	SECCOMP_ALLOW_SYSCALL(filter, timer_getoverrun);
	SECCOMP_ALLOW_SYSCALL(filter, timer_gettime);
	SECCOMP_ALLOW_SYSCALL(filter, timer_settime);
	SECCOMP_ALLOW_SYSCALL(filter, times);
	SECCOMP_ALLOW_SYSCALL(filter, tkill);
	SECCOMP_ALLOW_SYSCALL(filter, truncate);
	SECCOMP_ALLOW_SYSCALL(filter, truncate64);
	SECCOMP_ALLOW_SYSCALL(filter, ugetrlimit);
	SECCOMP_ALLOW_SYSCALL(filter, umask);
	SECCOMP_ALLOW_SYSCALL(filter, uname);
	SECCOMP_ALLOW_SYSCALL(filter, unlink);
	SECCOMP_ALLOW_SYSCALL(filter, unlinkat);
	SECCOMP_ALLOW_SYSCALL(filter, utime);
	SECCOMP_ALLOW_SYSCALL(filter, utimensat);
	SECCOMP_ALLOW_SYSCALL(filter, utimes);
	SECCOMP_ALLOW_SYSCALL(filter, vfork);
	SECCOMP_ALLOW_SYSCALL(filter, vmsplice);
	SECCOMP_ALLOW_SYSCALL(filter, wait4);
	SECCOMP_ALLOW_SYSCALL(filter, waitid);
	SECCOMP_ALLOW_SYSCALL(filter, waitpid);
	SECCOMP_ALLOW_SYSCALL(filter, write);
	SECCOMP_ALLOW_SYSCALL_LAST(filter, writev);
	if (seccomp_load(filter) != 0) {
		PANIC("Failed to load seccomp filter");
	}
	seccomp_release(filter);
	SUCCESS("Applied seccomp profile.");
}


int main(const int argc, char** argv) {
	struct ContainerContext context = defineIntendedContext(argc, argv);
	gatherHostInfo(&context);
	enterControlGroup(&context);
	changeRoot(&context);
	enterNamespaces();
	setupContainerMounts(&context);
	setContainerHostname(&context);
	dropCapabilities(&context);
	setupSeccomp();
	execPayload(&context);
}
