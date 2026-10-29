"""Update due competitors from the command line or Windows Task Scheduler (uses API quota)."""
import argparse
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path

import monitor
from research_agent import error_message, missing_keys

STATUS_TEXT = {'ok': '完成', 'failed': '失敗', 'skipped': '略過'}


def main(argv=None):
    parser = argparse.ArgumentParser(description='GNTC 競品監測：更新到期的競品（會使用 Gemini 與 Tavily 額度）')
    parser.add_argument('--all', action='store_true', help='更新所有啟用中的競品，不論是否到期')
    parser.add_argument('--log', type=Path, help='把輸出附加到這個檔案（排程在背景執行時使用）')
    args = parser.parse_args(argv)
    if not args.log:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        return _run(args)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with open(args.log, 'a', encoding='utf-8') as log, redirect_stdout(log), redirect_stderr(log):
        print(f'\n===== {datetime.now():%Y-%m-%d %H:%M:%S} 競品監測開始 =====', flush=True)
        try:
            code = _run(args)
        except Exception as exc:
            print(f'執行失敗：{error_message(exc)}', flush=True)
            code = 1
        print(f'===== 結束（exit code {code}） =====', flush=True)
        return code


def _run(args):
    missing = missing_keys()
    if missing:
        print('尚未設定：' + '、'.join(missing) + '。請填入專案 .env 後重試。')
        return 2
    outcomes = monitor.run_due(include_all=args.all,
                               on_start=lambda c: print(f'更新：{c["name"]}', flush=True),
                               progress=lambda n, text: print(f'  [{n}%] {text}', flush=True))
    if not outcomes:
        print('沒有到期需要更新的競品。')
        return 0
    print('\n結果：')
    for outcome in outcomes:
        print(f'- {outcome["competitor"]["name"]}：{STATUS_TEXT[outcome["status"]]}，{outcome["message"]}')
    return 1 if any(o['status'] != 'ok' for o in outcomes) else 0


if __name__ == '__main__':
    raise SystemExit(main())
