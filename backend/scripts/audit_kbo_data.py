"""Read-only data audit; save official HTML evidence and comparison reports separately."""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

from backend.scripts.collect_pitcher_stats import RecordPage, PREFIX, KBO_CODES
from backend.scripts.build_pitcher_stats import TEAM_NAMES, parse_ip

ROOT = Path(__file__).resolve().parents[2]
RANK_URL = 'https://www.koreabaseball.com/Record/TeamRank/TeamRank.aspx'
PITCHER_URL = 'https://www.koreabaseball.com/Record/Player/PitcherBasic/Basic1.aspx'


class Tables(HTMLParser):
    """Independent header-based table reader, not the collection row-index parser."""
    def __init__(self, html):
        super().__init__()
        self.tables, self.table, self.row, self.cell = [], None, None, None
        self.link = ''
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table':
            self.table = []
        elif tag == 'tr' and self.table is not None:
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell, self.link = [], ''
        elif tag == 'a' and self.cell is not None and 'playerId=' in attrs.get('href', ''):
            self.link = attrs['href']

    def handle_data(self, value):
        if self.cell is not None:
            self.cell.append(value)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append((' '.join(''.join(self.cell).split()), self.link))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            self.tables.append(self.table)
            self.table = None

    def records(self, required):
        for table in self.tables:
            for index, row in enumerate(table):
                headers = [cell[0] for cell in row]
                if required.issubset(headers):
                    return [dict(zip(headers, cells)) for cells in table[index + 1:] if len(cells) == len(headers)]
        raise ValueError(f'Official table headers not found: {required}')


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--official', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/validation')
    args = parser.parse_args()
    checked_at = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')
    run = args.output / datetime.now().strftime('%Y%m%d_%H%M%S')
    run.mkdir(parents=True, exist_ok=False)
    results, errors = [], []
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0'

    def record(season, team, item, local, official, source='', evidence='', status=None):
        results.append(dict(season=season, team=team, item=item, collected=local,
            official=official, difference='' if local == official else f'{local} != {official}',
            source=source, checked_at=checked_at, evidence=evidence,
            verdict=status or ('PASS' if local == official else 'MISMATCH')))

    def fetch(url, label, form=None):
        response = session.get(url, timeout=30) if form is None else session.post(url, data=form, timeout=30)
        response.raise_for_status()
        text = response.content.decode('utf-8-sig')
        evidence = run / f'{label}.html'
        evidence.write_text(text, encoding='utf-8')
        return text, evidence.name

    for season in range(2023, 2027):
        games = read(ROOT / f'data/games/game_results_{season}.csv')
        pitchers = read(ROOT / f'data/pitchers/pitcher_stats_{season}.csv')
        by_id, dates = defaultdict(list), defaultdict(set)
        for row in games:
            by_id[row['game_id']].append(row)
            dates[(row['date'], row['team'], row['opponent'])].add(row['game_id'])
            expected = 'W' if int(row['runs_for']) > int(row['runs_against']) else 'L' if int(row['runs_for']) < int(row['runs_against']) else 'D'
            if row['result'] != expected or row['status'] != 'completed' or int(row['season']) != season:
                errors.append(f'{season}: invalid game {row["game_id"]}')
        record(season, 'ALL', 'unique game/team rows', len(games), len({(r['game_id'],r['team']) for r in games}))
        bad_pairs = 0
        for pair in by_id.values():
            if len(pair) != 2:
                bad_pairs += 1
                continue
            a, b = pair
            if any(a[k] != b[k] for k in ('date','season','status','stadium')) or a['team'] != b['opponent'] or a['opponent'] != b['team'] or a['home_away'] == b['home_away'] or a['runs_for'] != b['runs_against'] or a['runs_against'] != b['runs_for']:
                bad_pairs += 1
        record(season, 'ALL', 'inconsistent game pairs', bad_pairs, 0)
        # Same-day two-game pairs are retained, not silently merged.
        suspicious = [dict(date=key[0], team=key[1], opponent=key[2], ids=sorted(ids)) for key,ids in dates.items() if len(ids)>1 and (len(ids)>2 or {i[-1] for i in ids}!={'1','2'})]
        record(season, 'ALL', 'suspicious same-day IDs', len(suspicious), 0)
        if suspicious:
            (run / f'suspected_duplicates_{season}.json').write_text(json.dumps(suspicious,ensure_ascii=False,indent=2),encoding='utf-8')
        record(season, 'ALL', 'pitcher rows', len(pitchers), 30)
        record(season, 'ALL', 'unique pitcher keys', len(pitchers),len({(r['season'],r['team_code'],r['player_id']) for r in pitchers}))
        for r in pitchers:
            if any(not math.isfinite(float(r[k])) or float(r[k]) < 0 for k in ('innings','era','whip','games_appeared','earned_runs','strikeouts')):
                errors.append(f'{season}: invalid pitcher {r["player_id"]}')
        print(f'{season}: internal checks done',flush=True)
        if not args.official:
            continue
        try:
            html, evidence = fetch(RANK_URL, f'rank_{season}_initial')
            form = RecordPage(html).form
            field = next(k for k in form if k.endswith('$ddlYear'))
            form.update({field:str(season),'__EVENTTARGET':field,'__EVENTARGUMENT':''})
            html, evidence = fetch(RANK_URL, f'rank_{season}',form)
            if RecordPage(html).form.get(field) != str(season):
                raise ValueError('Rank season filter not applied')
            official_rows = Tables(html).records({'팀명','경기','승','패','무'})
            for team in TEAM_NAMES.values():
                matches = [r for r in official_rows if r['팀명'][0]==team]
                if len(matches)!=1:
                    raise ValueError(f'Rank missing/ambiguous team {team}')
                counts = Counter(r['result'] for r in games if r['team']==team)
                for field,key in [('경기',None),('승','W'),('패','L'),('무','D')]:
                    local = sum(counts.values()) if key is None else counts[key]
                    record(season,team,field,local,int(matches[0][field][0]),RANK_URL,evidence)
        except Exception as exc:
            record(season,'ALL','official rank check','',repr(exc),RANK_URL,status='UNVERIFIED')
        for code,team in TEAM_NAMES.items():
            try:
                html,_ = fetch(PITCHER_URL,f'pitcher_{season}_{code}_initial')
                form = RecordPage(html).form
                field = PREFIX+'ddlSeason$ddlSeason'
                if form.get(field)!=str(season):
                    form.update({field:str(season),'__EVENTTARGET':field,'__EVENTARGUMENT':''})
                    html,_=fetch(PITCHER_URL,f'pitcher_{season}_{code}_season',form)
                    form=RecordPage(html).form
                expected={field:str(season),PREFIX+'ddlSeries$ddlSeries':'0',PREFIX+'ddlTeam$ddlTeam':KBO_CODES[code],PREFIX+'hfOrderByCol':'INN2_CN',PREFIX+'hfOrderBy':'DESC'}
                form.update(expected)
                form.update({'__EVENTTARGET':PREFIX+'lbtnOrderBy','__EVENTARGUMENT':'',PREFIX+'hfPage':'1'})
                html,evidence=fetch(PITCHER_URL,f'pitcher_{season}_{code}',form)
                returned=RecordPage(html).form
                if any(returned.get(k)!=v for k,v in expected.items()):
                    raise ValueError('Pitcher official filters not applied')
                official=Tables(html).records({'선수명','팀명','ERA','G','IP','ER','WHIP','SO'})
                ranked=[]
                for r in official:
                    if parse_ip(r['IP'][0])>0:
                        pid=parse_qs(urlparse(r['선수명'][1]).query)['playerId'][0]
                        ranked.append((r,pid))
                ranked.sort(key=lambda pair:(-parse_ip(pair[0]['IP'][0]),pair[1]))
                local=[r for r in pitchers if r['team_code']==code]
                record(season,team,'IP top3 player IDs',sorted(r['player_id'] for r in local), sorted(pid for r,pid in ranked[:3]),PITCHER_URL,evidence)
                for row in local:
                    r=next(r for r,pid in ranked if pid==row['player_id'])
                    record(season,team,f'{row["player_id"]}: name',row['player'],r['선수명'][0],PITCHER_URL,evidence)
                    for dest,source in [('games_appeared','G'),('innings','IP'),('earned_runs','ER'),('era','ERA'),('whip','WHIP'),('strikeouts','SO')]:
                        value=round(parse_ip(r[source][0]),4) if source=='IP' else float(r[source][0])
                        record(season,team,f'{row["player_id"]}: {dest}',float(row[dest]),value,PITCHER_URL,evidence)
                print(f'{season} {code}: official pitcher comparison done',flush=True)
            except Exception as exc:
                record(season,team,'official pitcher check','',str(exc),PITCHER_URL,status='UNVERIFIED')
    for error in errors:
        record('', 'ALL','internal validation error','',error,status='MISMATCH')
    with (run/'comparisons.csv').open('w',encoding='utf-8-sig',newline='') as fp:
        writer=csv.DictWriter(fp,fieldnames=list(results[0]))
        writer.writeheader();writer.writerows(results)
    summary=dict(checked_at=checked_at,counts=dict(Counter(r['verdict'] for r in results)),report=str(run),
        scope='Internal checks + official ranking and header-based pitcher comparison; game detail and traded-player split semantics not independently verified.',
        evidence_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in run.glob('*.html')})
    (run/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='evidence_sha256'},ensure_ascii=True),flush=True)


if __name__=='__main__':
    main()
