#!/usr/bin/env python3
"""
Script to verify event store integrity.

This script checks the hash chain of all event streams to detect
any tampering or corruption.

Usage:
    python scripts/verify_events.py
    python scripts/verify_events.py --stream agent:abc123
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import distinct, select

from agent_polis.events.models import Event
from agent_polis.events.store import EventStore
from agent_polis.shared.db import async_session_factory, init_db


async def verify_all_streams():
    """Verify all event streams."""
    await init_db()

    async with async_session_factory() as session:
        store = EventStore(session)

        # Get all unique stream IDs
        result = await session.execute(
            select(distinct(Event.stream_id))
        )
        stream_ids = [row[0] for row in result.all()]

        print(f"Found {len(stream_ids)} event streams to verify\n")

        valid_count = 0
        invalid_count = 0

        for stream_id in stream_ids:
            is_valid = await store.verify_stream_integrity(stream_id)

            if is_valid:
                print(f"✓ {stream_id}")
                valid_count += 1
            else:
                print(f"✗ {stream_id} - INTEGRITY FAILURE!")
                invalid_count += 1

        print(f"\n{'='*50}")
        print(f"Results: {valid_count} valid, {invalid_count} invalid")

        if invalid_count > 0:
            print("\n⚠️  WARNING: Some streams have integrity failures!")
            print("This could indicate tampering or data corruption.")
            return 1
        else:
            print("\n✓ All event streams verified successfully")
            return 0


async def verify_single_stream(stream_id: str):
    """Verify a single stream."""
    await init_db()

    async with async_session_factory() as session:
        store = EventStore(session)

        events = await store.get_stream(stream_id)

        if not events:
            print(f"No events found for stream: {stream_id}")
            return 1

        print(f"Verifying stream: {stream_id}")
        print(f"Events: {len(events)}")
        print()

        is_valid = await store.verify_stream_integrity(stream_id)

        if is_valid:
            print("✓ Stream integrity verified")

            # Show event chain
            print("\nEvent chain:")
            for event in events:
                print(f"  [{event.stream_version}] {event.event_type}")
                print(f"      Hash: {event.hash[:16]}...")
                if event.prev_hash:
                    print(f"      Prev: {event.prev_hash[:16]}...")

            return 0
        else:
            print("✗ INTEGRITY FAILURE!")
            return 1


async def main():
    parser = argparse.ArgumentParser(
        description="Verify event store integrity"
    )
    parser.add_argument(
        "--stream",
        help="Verify a specific stream (e.g., agent:abc123)",
    )

    args = parser.parse_args()

    if args.stream:
        return await verify_single_stream(args.stream)
    else:
        return await verify_all_streams()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
