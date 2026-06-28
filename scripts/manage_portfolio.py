"""
Portfolio management CLI.

Usage:
  python scripts/manage_portfolio.py list
  python scripts/manage_portfolio.py add
  python scripts/manage_portfolio.py remove TICKER
  python scripts/manage_portfolio.py retag TICKER TAG
  python scripts/manage_portfolio.py update TICKER field=value [field=value ...]
"""
import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.portfolio import (
    get_all_positions, add_position,
    remove_position, retag, update_position,
    list_tickers
)


def cmd_list():
    positions = get_all_positions()
    print(f"\n{'TICKER':<10} {'SLEEVE':<5} {'TAG':<14} {'WEIGHT':>7} {'THESIS':<10} NOTE")
    print("─" * 72)
    for p in positions:
        print(
            f"{p['ticker']:<10} {p['sleeve']:<5} {p['tag']:<14} {p['weight']*100:>6.1f}% {p['thesis_status']:<10} {p.get('thesis_note','')[:30]}"
        )
    print(f"\nTotal: {len(positions)} positions")


def cmd_add():
    print("\n── Add New Position ──")
    sleeve = input("Sleeve [US/HK]: ").strip().upper()
    ticker = input("Ticker (e.g. AAPL): ").strip().upper()
    tag = input("Tag [CORE/SATELLITE/PROBLEM/DEAD_WEIGHT/LEVERAGED]: ").strip().upper()
    weight = float(input("Weight as decimal (e.g. 0.05): "))
    thesis_note = input("Thesis note (one line): ").strip()
    thesis_status = input("Thesis status [Intact/Watch/Broken] (default Intact): ").strip() or "Intact"
    scale_trigger_str = input("Scale trigger price (Enter to skip): ").strip()
    scale_trigger = float(scale_trigger_str) if scale_trigger_str else None
    core_eligible_str = input("CORE eligible at price (Enter to skip): ").strip()
    core_eligible_at = float(core_eligible_str) if core_eligible_str else None
    pos = add_position(
        sleeve, ticker, tag, weight, thesis_note, thesis_status, scale_trigger, core_eligible_at
    )
    print(f"\n✅ Added {ticker} to {sleeve} sleeve:\n  {pos}")


def cmd_remove():
    if len(sys.argv) < 3:
        print("Usage: python scripts/manage_portfolio.py remove TICKER")
        sys.exit(1)
    ticker = sys.argv[2].upper()
    ok = remove_position(ticker)
    if ok:
        print(f"✅ Removed {ticker}")
    else:
        print(f"❌ {ticker} not found")


def cmd_retag():
    if len(sys.argv) < 4:
        print("Usage: python scripts/manage_portfolio.py retag TICKER NEW_TAG [NEW_THESIS_STATUS]")
        sys.exit(1)
    ticker = sys.argv[2].upper()
    new_tag = sys.argv[3].upper()
    new_thesis_status = sys.argv[4] if len(sys.argv) > 4 else None
    pos = retag(ticker, new_tag, new_thesis_status)
    if pos:
        print(f"✅ {ticker} → {new_tag} ({pos['thesis_status']})")
    else:
        print(f"❌ {ticker} not found")


def cmd_update():
    if len(sys.argv) < 4:
        print("Usage: python scripts/manage_portfolio.py update TICKER field1=value1 [field2=value2 ...]")
        sys.exit(1)
    ticker = sys.argv[2].upper()
    kwargs = {}
    for pair in sys.argv[3:]:
        key, value = pair.split("=", 1)
        try:
            # Try convert to float first for numeric values
            if "." in value or "e" in value.lower():
                kwargs[key] = float(value)
            else:
                try:
                    kwargs[key] = int(value)
                except ValueError:
                    # If not int, try float again in case it's like 0
                    kwargs[key] = float(value)
        except ValueError:
            kwargs[key] = value
    pos = update_position(ticker, **kwargs)
    if pos:
        print(f"✅ Updated {ticker}: {kwargs}")
    else:
        print(f"❌ {ticker} not found")


COMMANDS = {
    "list": cmd_list,
    "add": cmd_add,
    "remove": cmd_remove,
    "retag": cmd_retag,
    "update": cmd_update,
}

if __name__ == "__main__":
    if len(sys.argv) == 1:
        cmd = "list"
    else:
        cmd = sys.argv[1].lower()
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}")
        print(f"Available commands: {', '.join(COMMANDS.keys())}")
        sys.exit(1)
    COMMANDS[cmd]()