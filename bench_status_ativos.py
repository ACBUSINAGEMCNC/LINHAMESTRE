import argparse
import os
import json
import time
from urllib.parse import urlencode

from app import create_app


def run_once(client, params):
    qs = urlencode({k: v for k, v in params.items() if v is not None})
    url = f"/apontamento/status-ativos?{qs}" if qs else "/apontamento/status-ativos"
    t0 = time.perf_counter()
    resp = client.get(url)
    t_total = (time.perf_counter() - t0) * 1000
    if resp.status_code != 200:
        return {
            "ok": False,
            "status_code": resp.status_code,
            "error": resp.get_data(as_text=True)[:500],
            "client_total_ms": int(t_total),
        }

    data = resp.get_json(silent=True)
    if data is None:
        try:
            text = resp.get_data(as_text=True)
            data = json.loads(text)
        except Exception:
            data = {"raw": resp.get_data(as_text=True)[:500]}

    n_cards = len((data or {}).get("status_ativos", []) or [])
    timings = (data or {}).get("timings", {}) or {}
    timings_out = {k: int(v) for k, v in timings.items() if isinstance(v, (int, float))}
    timings_out["client_total_ms"] = int(t_total)

    return {
        "ok": True,
        "status_code": resp.status_code,
        "n_cards": n_cards,
        "timings": timings_out,
    }


def main():
    parser = argparse.ArgumentParser(description="Bench /apontamento/status-ativos")
    parser.add_argument("--lista", default=None, help="Filter lista kanban (case-insensitive)")
    parser.add_argument("--lista-tipo", dest="lista_tipo", default=None, help="Filter by lista tipo")
    parser.add_argument("--status", default=None, help="Filter by status (comma-separated)")
    parser.add_argument("-n", "--iterations", type=int, default=1, help="Number of iterations")
    parser.add_argument("--print-json", action="store_true", help="Print a sample of the JSON (first card only)")

    args = parser.parse_args()

    t_app0 = time.perf_counter()
    app = create_app()
    app_start_ms = int((time.perf_counter() - t_app0) * 1000)
    app.testing = True

    params = {
        "timing": "1",
        "lista": args.lista,
        "lista_tipo": args.lista_tipo,
        "status": args.status,
    }

    results = []
    print(f"App startup: {app_start_ms} ms (SKIP_DB_CHECKS={os.getenv('SKIP_DB_CHECKS')})")
    with app.test_client() as client:
        for i in range(args.iterations):
            res = run_once(client, params)
            results.append(res)
            if not res.get("ok"):
                print(f"[{i+1}] ERROR status={res.get('status_code')} client_total_ms={res['client_total_ms']} msg={res.get('error')}")
                continue
            t = res.get("timings", {})
            print(
                f"[{i+1}] cards={res.get('n_cards')} total_ms={t.get('total_ms','-')} client_ms={t.get('client_total_ms','-')} "
                f"status_q={t.get('status_ativos_query_ms','-')} os_q={t.get('os_em_maquinas_query_ms','-')} build_status={t.get('build_status_loop_ms','-')} build_os={t.get('build_os_sem_ativos_loop_ms','-')}"
            )

        # Aggregate if multiple runs
        oks = [r for r in results if r.get("ok")]
        if len(oks) > 1:
            def collect(key):
                vals = [r["timings"].get(key) for r in oks if r.get("timings") and r["timings"].get(key) is not None]
                return vals

            keys = [
                "total_ms",
                "client_total_ms",
                "status_ativos_query_ms",
                "os_em_maquinas_query_ms",
                "build_status_loop_ms",
                "build_os_sem_ativos_loop_ms",
            ]
            print("\nAggregates (ms):")
            for k in keys:
                vals = collect(k)
                if not vals:
                    continue
                print(f"  {k}: min={min(vals)} avg={int(sum(vals)/len(vals))} max={max(vals)}")

        if args.print_json and oks:
            sample = oks[0]
            # fetch full JSON for first run again to print sample
            res = run_once(app.test_client(), params)
            data = res if not res.get("ok") else None
            if not data:
                with app.test_client() as client2:
                    r = client2.get(f"/apontamento/status-ativos?{urlencode(params)}")
                    data = r.get_json()
            print("\nSample JSON (first status only):")
            if isinstance(data, dict) and data.get("status_ativos"):
                preview = {**data}
                preview["status_ativos"] = data["status_ativos"][:1]
                print(json.dumps(preview, ensure_ascii=False, indent=2)[:2000])
            else:
                print(str(data)[:2000])


if __name__ == "__main__":
    main()
