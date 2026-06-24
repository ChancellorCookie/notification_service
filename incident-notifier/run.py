#!/usr/bin/env python3
"""Einstiegspunkt: python run.py /etc/incident-notifier/config.yaml"""
import os
import sys

from notifier.service import Service


def main():
    cfg = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "INCIDENT_NOTIFIER_CONFIG", "/etc/incident-notifier/config.yaml"
    )
    Service(cfg).run()


if __name__ == "__main__":
    main()
