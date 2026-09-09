"""Regenerate the committed GraphQL SDL snapshot.

``schema.graphql`` at the repo root is the checked-in rendering of
:data:`kabinet_server.schema.schema`. ``tests/test_print_schema.py`` fails when the
two disagree, so every schema change shows up as a reviewable diff of that file
instead of only as a behaviour change.

    python manage.py printschema            # rewrite schema.graphql in place
    python manage.py printschema --check    # exit 1 if it is out of date
    python manage.py printschema --stdout   # print the SDL instead of writing

Consumers regenerate from this file: the turms client in ``packages/kabinet`` and
the snapshot mounted into the rekuest container at
``deployments/next/configs/schemas/kabinet_v1.graphql``.
"""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from kabinet_server.schema import schema

#: Repo-root ``schema.graphql``, four parents up from this module.
SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schema.graphql"


def render_sdl() -> str:
    """Return the SDL for the live schema, newline-terminated."""
    return str(schema).strip() + "\n"


class Command(BaseCommand):
    """Write, check or print the SDL snapshot."""

    help = "Regenerate the committed schema.graphql SDL snapshot."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register the command's flags."""
        parser.add_argument(
            "--check",
            action="store_true",
            help="Do not write; exit non-zero if schema.graphql is out of date.",
        )
        parser.add_argument(
            "--stdout",
            action="store_true",
            help="Write the SDL to stdout instead of to schema.graphql.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Render the schema and write, diff or print it."""
        sdl = render_sdl()

        if options.get("stdout"):
            self.stdout.write(sdl)
            return

        if options.get("check"):
            current = SCHEMA_PATH.read_text() if SCHEMA_PATH.exists() else ""
            if current == sdl:
                self.stdout.write(self.style.SUCCESS(f"{SCHEMA_PATH.name} is up to date."))
                return
            diff = "".join(
                difflib.unified_diff(
                    current.splitlines(keepends=True),
                    sdl.splitlines(keepends=True),
                    fromfile=f"{SCHEMA_PATH.name} (committed)",
                    tofile=f"{SCHEMA_PATH.name} (rendered)",
                )
            )
            raise CommandError(f"{SCHEMA_PATH.name} is out of date. Run `python manage.py printschema`.\n\n{diff}")

        SCHEMA_PATH.write_text(sdl)
        self.stdout.write(self.style.SUCCESS(f"Wrote {SCHEMA_PATH}"))
