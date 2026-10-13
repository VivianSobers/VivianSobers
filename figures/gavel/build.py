"""Draw one auction's ordered event log from source fixtures."""

import json
import sys
from functools import cache
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from figkit.cli import main
from figkit.color import BLUE, EMBER, FAINT, INK, MUTED
from figkit.svg import document
from figkit.text import Face, Outliner

HERE = Path(__file__).resolve().parent


@cache
def faces():
    fonts = ROOT / 'figkit' / 'fonts'
    return {
        'title': Face(fonts / 'MonaSansVF[wdth,opsz,wght].ttf', {'wdth': 100, 'wght': 600}),
        'body': Face(fonts / 'MonaSansVF[wdth,opsz,wght].ttf', {'wdth': 100, 'wght': 430}),
        'number': Face(fonts / 'MonaspaceNeonVar.ttf', {'wght': 400}),
    }


def layout(data):
    chips = [(40, 112 + index * 54, 280, 44) for index in range(len(data['requests']))]
    width = (390 - 2 * (len(data['events']) - 1)) / len(data['events'])
    cells = [(850 + index * (width + 2), 165, width, 88)
             for index in range(len(data['events']))]
    return chips + [(425, 165, 300, 88)] + cells


def render(data, mode, freeze_at=None):
    face, out = faces(), Outliner()

    def text(label, x, y, size=15, kind='body', color=None, anchor='start'):
        return (f'<g fill="{color or INK[mode]}">'
                f'{out.run(face[kind], label, x, y, size, anchor)}</g>')

    def box(x, y, w, h, color):
        return (f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="8" '
                f'fill="{color}" fill-opacity="0.08" stroke="{color}" stroke-width="1"/>')

    title = 'Every auction is one ordered log'
    subtitle = 'Gleam decides, Elixir serializes, PostgreSQL fences each append on (auction, seq).'
    body = [text(title, 40, 44, 22, 'title'), text(subtitle, 40, 70, color=MUTED[mode])]
    body += [text('Incoming bids', 40, 102, 13, color=MUTED[mode]),
             text('One auction process', 425, 143, 13, color=MUTED[mode]),
             text('PostgreSQL event log', 850, 143, 13, color=MUTED[mode])]
    boxes = layout(data)
    chip_boxes = boxes[:len(data['requests'])]
    body.append(f'<path d="M320 134H375V296H320M375 209H425M725 209H850" '
                f'fill="none" stroke="{MUTED[mode]}" stroke-width="2" stroke-linecap="round"/>'
                f'<path d="M417 205L425 209L417 213M842 205L850 209L842 213" '
                f'fill="none" stroke="{MUTED[mode]}" stroke-width="2" stroke-linecap="round"/>')
    for row, (x, y, w, h) in zip(data['requests'], chip_boxes):
        color = EMBER[mode] if row['outcome'] == 'rejected' else BLUE[mode]
        label = f"{row['amount']} {data['config']['amount_unit']}   {row['request_id']}"
        outcome = 'retry' if row['outcome'] == 'duplicate' else row['outcome']
        body.append(f'<g class="bid-chip" aria-label={quoteattr(label + ": " + outcome)}>'
                    f'{box(x, y, w, h, color)}{text(label, x + 12, y + 19, 14, "number")}'
                    f'{text(outcome, x + 12, y + 36, 13, color=color)}</g>')
        if 134 < y + h / 2 < 296:
            body.append(f'<path d="M320 {y + h / 2:g}H375" stroke="{MUTED[mode]}" stroke-width="2"/>')
    body += [box(425, 165, 300, 88, FAINT[mode]),
             text('Auction process', 575, 191, anchor='middle'),
             text('(Gleam rules)', 575, 215, anchor='middle'),
             text('Elixir GenServer', 575, 238, 13, color=MUTED[mode], anchor='middle')]
    descriptions = []
    for event, (x, y, w, h) in zip(data['events'], boxes[len(data['requests']) + 1:]):
        color = BLUE[mode] if event['type'] == 'bid_accepted' else MUTED[mode]
        label = f"seq {event['seq']}"
        amount = (f"{event['amount']} {data['config']['amount_unit']}"
                  if event['type'] == 'bid_accepted' else 'opened')
        request = event.get('request_id', 'auction created')
        descriptions.append(f'{label}: {amount}, {request}')
        body.append(f'<g class="log-cell" data-seq="{event["seq"]}" aria-label={quoteattr(label + ": " + amount)}>'
                    f'{box(x, y, w, h, color)}{text(label, x + w / 2, y + 25, 14, "number", color, "middle")}'
                    f'{text(amount, x + w / 2, y + 51, 14, "number", anchor="middle")}'
                    f'{text(request, x + w / 2, y + 74, 13, "number", MUTED[mode], "middle")}</g>')
    rejected = next(row for row in data['requests'] if row['outcome'] == 'rejected')
    duplicate = next(row for row in data['requests'] if row['outcome'] == 'duplicate')
    rejection = 'rejected: below minimum'
    returned = 'same outcome returned'
    body += [f'<g class="rejection">{text(rejection, 425, 283, 15, color=EMBER[mode])}</g>',
             text(f"minimum {rejected['minimum']} {data['config']['amount_unit']}", 425, 303, 13, 'number', MUTED[mode]),
             f'<g class="duplicate">{text(returned, 850, 283, color=BLUE[mode])}</g>',
             text(f"{duplicate['request_id']}: original bid at seq {duplicate['original_seq']}", 850, 303, 13, 'number', MUTED[mode]),
             text(f"Unique {data['config']['sequence_fence']}", 850, 326, 13, 'number', MUTED[mode]),
             text('Illustrative source test fixtures. Amounts in cents; rejected bids and retries add no event.',
                  40, 352, 13, color=MUTED[mode])]
    desc = (f"{data['config']['basis']}. Auction: {data['config']['auction_title']}. "
            + '; '.join(descriptions)
            + f". {rejected['request_id']}: {rejected['amount']} cents, {rejection}, minimum {rejected['minimum']} cents. "
            + f"{duplicate['request_id']} retried: {returned}, original bid with the current view, no append. "
            + f"Sequence primary key {data['config']['sequence_fence']}; unique request index {data['config']['request_fence']}.")
    return document(1280, 380, title, desc, '', out.defs(), ''.join(body), freeze_at)


if __name__ == '__main__':
    main('gavel', HERE, render, json.loads((HERE / 'data.json').read_text()))
