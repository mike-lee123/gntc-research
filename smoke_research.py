"""Run a real, billable end-to-end research after configuring .env."""
import argparse
from pathlib import Path

from research_agent import error_message, missing_keys, research


def main():
    parser = argparse.ArgumentParser(description='GNTC 真實搜尋與報告驗證（會使用 API 額度）')
    parser.add_argument('topic', help='具體且範圍小的研究主題')
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'outputs' / 'smoke-report.md')
    args = parser.parse_args()
    missing = missing_keys()
    if missing:
        print('尚未設定：' + '、'.join(missing) + '。請填入專案 .env 後重試。')
        return 2
    if not args.topic.strip() or len(args.topic) > 4000:
        print('請提供 1 至 4000 字元的研究主題。')
        return 2
    try:
        result = research(args.topic, progress=lambda n, text: print(f'[{n}%] {text}', flush=True))
    except Exception as exc:
        print(error_message(exc))
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.report, encoding='utf-8')
    print(f'完成：{len(result.sources)} 個來源，報告已儲存至 {args.output.resolve()}')
    print('請人工核對繁體中文、各段落與引用是否支持報告陳述。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
