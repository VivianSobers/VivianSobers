"""Draw one auction's ordered event log from source fixtures."""

import json
import sys
from functools import cache
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from figkit.cli import main
from figkit.color import CATEGORICAL, FAINT, INK, MUTED, STATUS
from figkit.svg import delay, document
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
    chips = [(40, 112 + index * 58, 280, 50) for index in range(len(data['requests']))]
    width = (460 - 2 * (len(data['events']) - 1)) / len(data['events'])
    cells = [(780 + index * (width + 2), 165, width, 88)
             for index in range(len(data['events']))]
    return chips + [(425, 165, 300, 88)] + cells


def render(data, mode, freeze_at=None):
    face, out = faces(), Outliner()

    def text(label, x, y, size=16, kind='body', color=None, anchor='start'):
        return (f'<g fill="{color or INK[mode]}">'
                f'{out.run(face[kind], label, x, y, size, anchor)}</g>')

    def box(x, y, w, h, color, tint=0.08):
        return (f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="8" '
                f'fill="{color}" fill-opacity="{tint:g}" stroke="{color}" stroke-width="1.5"/>')

    title = 'Every auction is one ordered log'
    subtitle = 'Gleam decides, Elixir serializes, PostgreSQL fences each append on (auction, seq).'
    body = [text(title, 40, 44, 26, 'title'), text(subtitle, 40, 72, 18, color=MUTED[mode])]
    body += [text('Incoming bids', 40, 102, 16, color=MUTED[mode]),
             text('One auction process', 425, 145, 16, color=MUTED[mode]),
             text('PostgreSQL event log', 780, 145, 16, color=MUTED[mode])]
    css = ['.log-cell,.rejection,.duplicate{opacity:1}', '.traveler{opacity:0}']

    def keyframes(name, points):
        rules = ''.join(f'{100 * t / 14:.3f}%{{{value}}}' for t, value in points)
        css.append(f'@keyframes {name}{{{rules}}}')

    def style(name):
        return f'animation:{name} 14s ease-in-out infinite;{delay(0, freeze_at)}'

    decisions = {}
    for index, row in enumerate(data['requests']):
        start = 0.6 + index * 2.4
        decision = start + 1.1
        name = {'accepted': 'append', 'rejected': 'reject', 'duplicate': 'returned'}[row['outcome']] + str(index)
        decisions[index] = name
        keyframes(name, [(0, 'opacity:0'), (decision - 0.1, 'opacity:0'),
                         (decision, 'opacity:1'), (13.25, 'opacity:1'), (14, 'opacity:0')])
    boxes = layout(data)
    chip_boxes = boxes[:len(data['requests'])]
    process_box = boxes[len(data['requests'])]
    cell_boxes = boxes[len(data['requests']) + 1:]

    y_top = chip_boxes[0][1] + chip_boxes[0][3] / 2
    y_bot = chip_boxes[-1][1] + chip_boxes[-1][3] / 2
    x_proc = process_box[0]
    x_proc_end = process_box[0] + process_box[2]
    x_log = cell_boxes[0][0]

    body.append(f'<g style="{style("rules")}"><path d="M320 {y_top:g}H375V{y_bot:g}H320M375 209H{x_proc:g}M{x_proc_end:g} 209H{x_log:g}" '
                f'fill="none" stroke="{MUTED[mode]}" stroke-width="2.5" stroke-linecap="round"/>'
                f'<path d="M{x_proc - 10:g} 204L{x_proc:g} 209L{x_proc - 10:g} 214M{x_log - 10:g} 204L{x_log:g} 209L{x_log - 10:g} 214" '
                f'fill="none" stroke="{MUTED[mode]}" stroke-width="2.5" stroke-linecap="round"/></g>')
    travelers = []
    for index, (row, (x, y, w, h)) in enumerate(zip(data['requests'], chip_boxes)):
        color = {'accepted': STATUS['good'], 'rejected': STATUS['critical'],
                 'duplicate': CATEGORICAL['violet'][mode]}[row['outcome']]
        tint = 0.15 if row['outcome'] == 'accepted' else 0.08
        label = f"{row['amount']} {data['config']['amount_unit']}   {row['request_id']}"
        outcome = 'retry' if row['outcome'] == 'duplicate' else row['outcome']
        start = 0.6 + index * 2.4
        dx, dy = 435 - x, 187 - y
        rest = 'opacity:0;transform:translate(0px,0px)'
        at_source = 'opacity:1;transform:translate(0px,0px)'
        at_process = f'opacity:1;transform:translate({dx:g}px,{dy:g}px)'
        departing = (f'opacity:1;transform:translate({dx - 45:g}px,{dy:g}px)'
                     if row['outcome'] == 'rejected' else at_process)
        keyframes(f'travel{index}', [(0, rest), (start, rest), (start + 0.1, at_source),
                                   (start + 0.7, at_process), (start + 1.1, at_process),
                                   (start + 1.4, departing),
                                   (start + 1.6, departing.replace('opacity:1', 'opacity:0')),
                                   (start + 1.61, rest), (14, rest)])
        keyframes(f'chip{index}', [(0, 'opacity:0.25'), (start, 'opacity:0.25'),
                                 (start + 0.1, 'opacity:0.15'), (start + 1.6, 'opacity:1'),
                                 (13.25, 'opacity:1'), (14, 'opacity:0.25')])
        travelers.append(f'<g class="traveler" data-outcome="{row["outcome"]}" '
                         f'style="{style(f"travel{index}")}" aria-hidden="true">'
                         f'{box(x, y, w, h, color, tint)}{text(label, x + 14, y + 20, 16, "number")}</g>')
        body.append(f'<g class="bid-chip" style="{style(f"chip{index}")}" aria-label={quoteattr(label + ": " + outcome)}>'
                    f'{box(x, y, w, h, color, tint)}{text(label, x + 14, y + 20, 16, "number")}'
                    f'{text(outcome, x + 14, y + 43, 16)}</g>')
        if y_top < y + h / 2 < y_bot:
            body.append(f'<path style="{style("rules")}" d="M320 {y + h / 2:g}H375" stroke="{MUTED[mode]}" stroke-width="2.5"/>')
    process_frames = [(0, 'opacity:1')]
    for index in range(len(data['requests'])):
        start = 0.6 + index * 2.4
        process_frames += [(start, 'opacity:1'), (start + 0.1, 'opacity:0'),
                           (start + 1.4, 'opacity:0'), (start + 1.7, 'opacity:1')]
    keyframes('rules', process_frames + [(14, 'opacity:1')])
    x_proc_mid = x_proc + process_box[2] / 2
    body += [box(process_box[0], process_box[1], process_box[2], process_box[3], FAINT[mode]),
             f'<g style="{style("rules")}">',
             text('Auction process', x_proc_mid, 192, 16, anchor='middle'),
             text('(Gleam rules)', x_proc_mid, 216, 16, anchor='middle'),
             text('Elixir GenServer', x_proc_mid, 240, 16, color=MUTED[mode], anchor='middle'), '</g>']
    descriptions = []
    for event, (x, y, w, h) in zip(data['events'], cell_boxes):
        color = STATUS['good'] if event['type'] == 'bid_accepted' else MUTED[mode]
        tint = 0.15 if event['type'] == 'bid_accepted' else 0.08
        label = f"seq {event['seq']}"
        amount = (f"{event['amount']} {data['config']['amount_unit']}"
                  if event['type'] == 'bid_accepted' else 'opened')
        request = event.get('request_id', 'auction created')
        descriptions.append(f'{label}: {amount}, {request}')
        animation = ''
        if event['type'] == 'bid_accepted':
            index = next(i for i, row in enumerate(data['requests'])
                         if row['outcome'] == 'accepted' and row['request_id'] == event['request_id'])
            animation = f' style="{style(decisions[index])}"'
        body.append(f'<g class="log-cell"{animation} data-seq="{event["seq"]}" aria-label={quoteattr(label + ": " + amount)}>'
                    f'{box(x, y, w, h, color, tint)}{text(label, x + w / 2, y + 25, 16, "number", color, "middle")}'
                    f'{text(amount, x + w / 2, y + 49, 16, "number", anchor="middle")}'
                    f'{text(request, x + w / 2, y + 73, 16, "number", MUTED[mode], "middle")}</g>')
    rejected = next(row for row in data['requests'] if row['outcome'] == 'rejected')
    duplicate = next(row for row in data['requests'] if row['outcome'] == 'duplicate')
    rejection = 'rejected: below minimum'
    returned = 'same outcome returned'
    rejection_index = data['requests'].index(rejected)
    duplicate_index = data['requests'].index(duplicate)
    body += [f'<g class="rejection" style="{style(decisions[rejection_index])}">'
             + text(rejection, 425, 280, 16, color=STATUS['critical'])
             + text(f"minimum {rejected['minimum']} {data['config']['amount_unit']}",
                    425, 304, 16, 'number', MUTED[mode]) + '</g>',
             f'<g class="duplicate" style="{style(decisions[duplicate_index])}">'
             + text(returned, x_log, 280, 16, color=CATEGORICAL['violet'][mode])
             + text(f"{duplicate['request_id']}: original bid at seq {duplicate['original_seq']}",
                    x_log, 304, 16, 'number', MUTED[mode]) + '</g>',
             text(f"Unique {data['config']['sequence_fence']}", x_log, 328, 16, 'number', MUTED[mode]),
             text('Illustrative source test fixtures. Amounts in cents; rejected bids and retries add no event.',
                  40, 360, 16, color=MUTED[mode])]
    body.extend(travelers)
    desc = (f"{data['config']['basis']}. Auction: {data['config']['auction_title']}. "
            + '; '.join(descriptions)
            + f". {rejected['request_id']}: {rejected['amount']} cents, {rejection}, minimum {rejected['minimum']} cents. "
            + f"{duplicate['request_id']} retried: {returned}, original bid with the current view, no append and no new cell. "
            + f"Sequence primary key {data['config']['sequence_fence']}; unique request index {data['config']['request_fence']}.")
    desc += ' Bids arrive in request order; only accepted bids reveal new cells, in a repeating animation.'
    return document(1280, 380, title, desc, ''.join(css), out.defs(), ''.join(body), freeze_at)


if __name__ == '__main__':
    main('gavel', HERE, render, json.loads((HERE / 'data.json').read_text()))
