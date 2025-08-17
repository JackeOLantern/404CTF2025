#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# USAGE:
#   ./extract_all_tar.sh [DIRECTORY_WITH_TARS] [OUTPUT_DIR]
# ENV:
#   SANITIZE_COLONS=1  -> remplace ":" par "_" à l'extraction (utile NTFS/SMB). Mettre à 0 pour désactiver.

BASE_DIR="${1:-.}"
OUT_DIR="${2:-extracted_archives}"
SANITIZE_COLONS="${SANITIZE_COLONS:-1}"

mkdir -p "$OUT_DIR"

# Trouver toutes les archives .tar* (sans planter si rien)
mapfile -d '' ARCHIVES < <(
  find "$BASE_DIR" -maxdepth 1 -type f \
    \( -iname '*.tar' -o -iname '*.tar.gz' -o -iname '*.tgz' \
       -o -iname '*.tar.bz2' -o -iname '*.tbz2' \
       -o -iname '*.tar.xz' -o -iname '*.txz' \) -print0
)

if ((${#ARCHIVES[@]} == 0)); then
  echo "Aucune archive .tar* trouvée dans: $BASE_DIR"
  exit 0
fi

ok=0; ko=0

# Fonction pour normaliser le nom du dossier cible
basename_for() {
  local f="$1" b
  b="$(basename "$f")"
  b="${b%.tar}"
  b="${b%.tar.gz}"; b="${b%.tgz}"
  b="${b%.tar.bz2}"; b="${b%.tbz2}"
  b="${b%.tar.xz}";  b="${b%.txz}"
  printf '%s' "$b"
}

for f in "${ARCHIVES[@]}"; do
  name="$(basename_for "$f")"
  dest="$OUT_DIR/$name"
  mkdir -p "$dest"

  echo "→ Extraction de: $f"
  # Options tar robustes
  TAR_OPTS=( --extract --auto-compress --file "$f" --directory "$dest"
             --no-same-owner --no-same-permissions --overwrite-dir )

  # Remplacer ":" par "_" (sécu/praticité sur NTFS/SMB). Mettre SANITIZE_COLONS=0 pour garder tel quel.
  if [[ "$SANITIZE_COLONS" == "1" ]]; then
    TAR_OPTS+=( --transform 's/:/_/g' )
  fi

  if tar "${TAR_OPTS[@]}" >/dev/null; then
    echo "   ✅ OK → $dest"
    ((ok++))
  else
    echo "   ❌ ERREUR → $f" >&2
    ((ko++))
  fi
done

echo
echo "=== BILAN ==="
echo "Succès : $ok"
echo "Échecs : $ko"
