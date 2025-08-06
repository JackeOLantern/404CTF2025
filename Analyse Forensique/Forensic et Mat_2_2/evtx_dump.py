
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import Evtx.Evtx as evtx

def main():
    parser = argparse.ArgumentParser(description="Dump records from EVTX file as XML.")
    parser.add_argument("evtx_file", help="Path to EVTX file")
    args = parser.parse_args()

    with evtx.Evtx(args.evtx_file) as log:
        for record in log.records():
            print(record.xml())

if __name__ == "__main__":
    main()
