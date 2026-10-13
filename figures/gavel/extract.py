"""Snapshot the bid examples asserted by the auction server tests."""

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PATHS = [
    'test/gavel/auction/server_bid_test.exs',
    'test/gavel/auction/server_duplicate_test.exs',
    'rules/src/gavel_rules/auction.gleam',
    'lib/gavel/auction/server.ex',
    'lib/gavel/store.ex',
    'lib/gavel/rules.ex',
    'priv/repo/migrations/20261012203933_create_auctions_and_events.exs',
]


def snapshot(repo: Path) -> dict:
    bid_test, duplicate_test, rules, server, store, interop, migration = [
        (repo / path).read_text() for path in PATHS
    ]
    example = duplicate_test.split('test "duplicate after subsequent bid')[1]
    commands = re.findall(r'\{:place_bid, "([^"]+)", "([^"]+)", ([\d_]+)\}', example)
    requests = [dict(request_id=request, bidder=bidder, amount=int(amount.replace('_', '')))
                for request, bidder, amount in commands]
    rejection = bid_test.split('test "rejected bid')[1]
    request, bidder, amount = re.search(
        r'\{:place_bid, "([^"]+)", "([^"]+)", ([\d_]+)\}', rejection).groups()
    minimum = int(re.search(r'\{:below_minimum, ([\d_]+)\}', rejection)[1].replace('_', ''))
    opened_seq = int(re.search(r'%EventRecord\{.*?seq: (\d+),', store, re.S)[1])
    first_seq = int(re.search(r'assert view.seq == (\d+)', duplicate_test)[1])
    last_seq = int(re.search(r'assert view2.seq == (\d+)', example)[1])
    assert first_seq == opened_seq + 1 and last_seq == first_seq + 1
    assert 'dict.get(state.accepted, request_id)' in rules
    assert '{:duplicate, bid, state.view}' in server
    assert '{:below_minimum, cents}' in interop
    assert 'primary_key: true' in migration and '[:auction_id, :request_id]' in migration
    events = [dict(seq=opened_seq, type='opened')]
    for seq, row in zip((first_seq, last_seq), requests[:2]):
        row.update(outcome='accepted', seq=seq)
        events.append(dict(seq=seq, type='bid_accepted', amount=row['amount'], request_id=row['request_id']))
    requests[-1].update(outcome='duplicate', original_seq=first_seq)
    requests.insert(0, dict(request_id=request, bidder=bidder,
                            amount=int(amount.replace('_', '')), minimum=minimum, outcome='rejected'))
    return {
        'source': {'repo': 'https://github.com/VivianSobers/gavel',
                   'commit': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(),
                   'paths': PATHS},
        'config': {'basis': 'illustrative source test fixtures, not a recorded run',
                   'amount_unit': 'cents', 'auction_title': re.search(r'title: "([^"]+)"', bid_test)[1],
                   'sequence_fence': '(auction_id, seq)',
                   'request_fence': '(auction_id, request_id)'},
        'requests': requests, 'events': events,
    }


if __name__ == '__main__':
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / 'gavel'
    (HERE / 'data.json').write_text(json.dumps(snapshot(repo), indent=2) + '\n')
