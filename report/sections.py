# -*- coding: utf-8 -*-
"""리포트 8장 조립.

────────────────────────────────────────────────────────────────────
자동으로 쓰는 장과 사람이 쓰는 장이 나뉜다. 가르는 질문은 하나다.

    이 문장이 틀렸을 때 누가 책임지는가?
        사람이 진다        → 사람이 쓴다   (2 배경 · 6 해석 · 8 제안)
        사실이 틀린 것뿐   → 자동으로 쓴다 (1 요약 · 3 방법 · 4 결과 · 5 실험 · 7 한계)

**해석과 제안을 자동화하는 순간 책임이 사라진다.** 그것이 이 수업의 결론이다.
────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from datetime import datetime

from core import config as C, metrics as M

# ★ 자동 생성 문장에 인과를 단정하는 말을 쓰지 않는다.
#   관측 데이터로는 인과를 주장할 수 없는데, 방심하면 자동 문장이 인과를 쓴다.
#   내 도메인에만 있는 단정 표현이 있으면 여기에 더한다.
#   8주차 금요일 — 회계세무팀 리포트에 흔한 표현을 더했다(기여하였다·제고·견인·주효·
#   성공적으로·유의미한 은 일반적인 단정 표현, 창출했다는 재무 보고서에 특히 흔하다).
BANNED = ["때문에", "덕분에", "효과로", "입증되었", "증명되었", "확실히",
          "기여하였다", "제고", "견인", "주효", "성공적으로", "유의미한", "창출했다"]


def check_phrasing(text: str) -> list[str]:
    """자동 생성 문장에 인과 단정 표현이 섞였는지 스스로 검사한다.

    **그대로 쓴다.** 사람이 쓴 장에도 걸어라 — 사람이 더 자주 쓴다.
    """
    return [w for w in BANNED if w in text]


def _fmt(n, unit=""):
    return f"{n:,.0f}{unit}"


# ── 자동으로 쓰는 장 ──────────────────────────────────────────────
def _s1_summary(t: dict) -> dict:
    """1. 요약 — 기간·주요 지표·가장 낮은 구간만. 원인은 넣지 않는다.

    8주차 금요일 확정 — metrics.kpis() 가 돌려주는 지표 이름을 그대로 쓴다.
    (이름을 기억해서 새로 적지 않는다 — 화요일에 카드가 바뀌었을 수 있다.)
    """
    df = t[C.TABLES[0]]
    k = M.kpis(t)
    f = M.funnel(df)
    lo, hi = C.PERIOD
    bi = int(f.index[f.is_bottleneck][0])

    lines = [f"분석 기간: {lo} ~ {hi} ({len(df):,}건)", ""]
    for name, v in k.items():
        lines.append(f"{name}: {v['fmt'].format(v['value'])}")
    lines.append("")
    lines.append(f"가장 낮은 전환 구간: {f.label.iloc[bi - 1]} → {f.label.iloc[bi]} "
                 f"({f.step_rate.iloc[bi] * 100:.1f}%)")
    return {"title": "1. 요약", "kind": "auto", "body": "\n".join(lines)}


def _s3_method(t: dict) -> dict:
    """3. 방법 — 그레인·기간·판정 기준. 결과는 넣지 않는다.

    8주차 금요일 확정.
    """
    df = t[C.TABLES[0]]
    lo, hi = C.PERIOD
    n = len(df)
    lines = [
        "분석 단위(그레인): 결산체크리스트 항목 1건(체크ID 고유값). 한 항목이 같은 "
        "단계를 두 번 밟지 않으므로 고유값 처리 없이 행을 그대로 센다.",
        "",
        f"데이터 기간: {lo} ~ {hi} ({n:,}건). 결측값 없음.",
        "",
        "퍼널 3단계: 등록(전체 행) → 완료(완료여부='Y') → 최종승인(최종승인='Y'). "
        "'Y' 문자열 정확 일치로 판정한다.",
        "",
        "비율 지표(최종승인율·완료율·재작업률)는 보정 없이 전체 건수를 그대로 분모로 "
        "쓴다. 관측 기간(12개월)이 다른 구간을 누적값으로 비교하지 않으며, 최근 등록분이 "
        "관측 시간 부족으로 낮게 잡히는 편향이 있는지 이미 확인했다 — 없었다(8주차 화요일).",
        "",
        "분해 축: 담당자. 담당자·계정과목·사업부 세 후보 중 격차가 가장 크고(24.7%p), "
        "모든 구간이 최소 표본(30건, config.MIN_SAMPLE) 이상이라 감춰지는 칸이 없어 "
        "선택했다(8주차 목요일).",
    ]
    return {"title": "3. 방법", "kind": "auto", "body": "\n".join(lines)}


# ★ 결과 장의 분해 축. 3장(방법)에 적은 축과 반드시 같아야 한다.
RESULT_DIM = "담당자"


def _s4_results(t: dict) -> dict:
    """4. 결과 — 단계별 값과 분해 결과만. "왜"는 6장(해석)으로 미룬다.

    8주차 금요일 확정.
    """
    df = t[C.TABLES[0]]
    f = M.funnel(df)
    bi = int(f.index[f.is_bottleneck][0])
    step_from, step_to = f.step.iloc[bi - 1], f.step.iloc[bi]
    g = M.funnel_by(df, df, RESULT_DIM, step_from, step_to)
    dim_col = g.columns[0]

    lines = ["[단계별 값]"]
    for r in f.itertuples():
        rate = f"{r.step_rate * 100:.1f}%" if r.step_rate == r.step_rate else "-"
        lines.append(f"  {r.label}: {r.n:,}건 (전 단계 대비 {rate})")

    lines.append("")
    lines.append(f"[분해 결과 — {RESULT_DIM}별 {f.label.iloc[bi - 1]}→{f.label.iloc[bi]} 전환율]")
    for r in g.itertuples():
        lines.append(f"  {getattr(r, dim_col)}: {r.도달}건 중 {r.전환}건 ({r.전환율 * 100:.1f}%)")

    best = g.loc[g["전환율"].idxmax()]
    worst = g.loc[g["전환율"].idxmin()]
    lines.append("")
    lines.append(f"{dim_col} 간 격차: {best[dim_col]}({best.전환율 * 100:.1f}%) - "
                 f"{worst[dim_col]}({worst.전환율 * 100:.1f}%) = "
                 f"{(best.전환율 - worst.전환율) * 100:.1f}%p")
    return {"title": "4. 결과", "kind": "auto", "body": "\n".join(lines),
            "charts": ["funnel", "device"]}


def _s5_experiments(t: dict) -> dict:
    """5. 실험 — 이 도메인엔 실험 테이블이 없다.

    ★ 「내 도메인이라면」— 실험 대신 반기(상반기/하반기) 전후 비교를 쓴다.
    무작위 배정이 없으므로 **"인과를 주장할 수 없다"를 본문 첫 문단에 넣는다**
    (각주가 아니라 본문에). 무효 판정이면 사유만 적고 수치를 쓰지 않는다
    (8주차 목요일 half_year_comparison() 이 무효일 때 계산 자체를 하지 않으므로,
    여기서는 애초에 r1·r2 같은 키가 없다 — 실수로 꺼내 쓸 수가 없다).
    """
    hc = M.half_year_comparison(t)
    lines = ["이 비교는 관측 데이터를 시점으로 나눈 전후 비교이며, 무작위 배정이 없었으므로 "
             "인과를 주장할 수 없다.", ""]
    if hc["verdict"] == "무효":
        lines.append(f"{hc['period_a']} vs {hc['period_b']}: 무효 — {hc['reason']}")
    else:
        lines.append(
            f"{hc['period_a']}({hc['n1']}건) vs {hc['period_b']}({hc['n2']}건) — "
            f"주지표 {hc['primary']} {hc['r1']:.1f}% → {hc['r2']:.1f}% "
            f"({hc['delta']:+.1f}%p), 가드레일 {hc['guardrail']} "
            f"{hc['g1']:.1f}% → {hc['g2']:.1f}% ({hc['g_delta']:+.1f}%p). "
            f"판정: {hc['verdict']}" + (f" — {hc['reason']}" if hc['reason'] else ""))
    return {"title": "5. 실험", "kind": "auto", "body": "\n".join(lines)}


def s7_limit_rows(t: dict) -> list[dict]:
    """한계 절 후보 행. [{"출처":.., "내용":..}, ...]. _s7_limits() 와 실습 G의
    편집 표(pages/3_리포트.py)가 함께 쓴다. 출처는 세 가지뿐이다.

        검증 경고        validate.run_checks() 에서 level == "warn" 인 것
        못 한 것         표본이 모자라 판정 못 한 것 · 데이터에 없어 못 본 것
        찾았는데 없음     찾아봤지만 신호가 없었던 것 — "없음"도 결과다

    8주차 금요일 확정.
    """
    from core import validate as V

    df = t[C.TABLES[0]]
    rows = [{"출처": "검증 경고", "내용": f"{w['name']}: {w['msg']}"}
            for w in V.run_checks(t) if w["level"] == "warn"]

    f = M.funnel(df)
    bi = int(f.index[f.is_bottleneck][0])
    step_from, step_to = f.step.iloc[bi - 1], f.step.iloc[bi]
    for dim in ["담당자", "계정과목", "사업부"]:
        g = M.funnel_by(df, df, dim, step_from, step_to)
        dim_col = g.columns[0]
        for r in g.itertuples():
            reason = M.trust_check(int(r.도달))
            if reason:
                rows.append({"출처": "못 한 것",
                              "내용": f"{dim_col}={getattr(r, dim_col)}: {reason}로 "
                                      f"{f.label.iloc[bi - 1]}→{f.label.iloc[bi]} "
                                      f"전환율을 판정하지 않았다"})

    rows.append({"출처": "못 한 것",
                 "내용": "유지 퍼널(계정과목×회계기간)은 칸당 표본이 1~7건뿐이라 "
                         "참고 신호로만 썼다(CLAUDE.md 유지 퍼널 절)."})
    rows.append({"출처": "못 한 것",
                 "내용": "최종승인자(결재자) 식별 컬럼과 재작업 사유 컬럼이 데이터에 "
                         "없어, 담당자 본인이 자기 항목을 승인했는지·재작업이 반복되는 "
                         "구체적 사유는 이 데이터로 확인할 수 없다."})
    rows.append({"출처": "찾았는데 없음",
                 "내용": "재작업(검토횟수 3회 이상)이 지연일수를 늘리는지 확인했으나, 재작업 "
                         "건의 평균 지연일수(1.1일)가 재작업이 아닌 건(1.4일)보다 "
                         "오히려 짧아 뚜렷한 관련이 없었다."})
    rows.append({"출처": "찾았는데 없음",
                 "내용": "월별 완료율 변동(표준편차 4.3%p)이 작아, 분기 말·연말에 "
                         "몰리는 계절성이라 부를 만한 패턴은 나타나지 않았다."})
    return rows


def _s7_limits(t: dict, rows: list[dict] | None = None) -> dict:
    """7. 한계 — 세 출처에서 조립한다. 화면에서 "포함"을 끈 행은 여기 안 들어온다.

    8주차 금요일 확정 — 인과 주장 불가·기간 한계 두 문장은 편집 대상이 아니라
    항상 붙는 정책 문구라서, 편집 가능한 rows 와 분리해 여기서 직접 붙인다.
    """
    if rows is None:
        rows = s7_limit_rows(t)
    lo, hi = C.PERIOD
    lines = [f"[{r['출처']}] {r['내용']}" for r in rows]
    if not any(r["출처"] == "검증 경고" for r in rows):
        lines.insert(0, "[검증 경고] 이번 실행에서는 warn 레벨 경고가 없었다 "
                        "(행 수·필수 컬럼·날짜 범위 모두 통과).")
    lines.append("관측 데이터이므로 인과를 주장할 수 없다.")
    lines.append(f"기간이 {lo} ~ {hi}이므로 그보다 긴 주기의 변화는 관측되지 않는다.")
    return {"title": "7. 한계", "kind": "auto", "body": "\n".join(lines)}


def human_guide(t: dict) -> dict[str, dict[str, list[str]]]:
    """2·6·8장(사람이 쓰는 장) 작성 가이드.

    **문장을 대신 써주지 않는다.** 실제 값을 참고 삼아 "이런 걸 설명하면
    좋다"는 항목만 안내하고, "담당자가 직접 결정할 내용"은 답을 주지 않고
    무엇을 정해야 하는지만 짚는다 — 결론은 사람이 낸다.

    반환: {장 제목: {"suggest": [...], "decide": [...]}}
    """
    df = t[C.TABLES[0]]
    lo, hi = C.PERIOD
    f = M.funnel(df)
    bi = int(f.index[f.is_bottleneck][0])
    g = M.funnel_by(df, df, RESULT_DIM, f.step.iloc[bi - 1], f.step.iloc[bi])
    dim_col = g.columns[0]
    best = g.loc[g["전환율"].idxmax()]
    worst = g.loc[g["전환율"].idxmin()]
    gap = (best["전환율"] - worst["전환율"]) * 100
    hidden_n = sum(1 for r in s7_limit_rows(t)
                   if r["출처"] == "못 한 것" and "판정하지 않았다" in r["내용"])
    hc = M.half_year_comparison(t)
    year = lo[:4] if lo[:4] == hi[:4] else f"{lo[:4]}~{hi[:4]}"

    return {
        "2. 배경": {
            "suggest": [
                f"왜 {year}년 {C.DATASET} 이행 현황을 점검하는지",
                f"병목 구간({f.label.iloc[bi - 1]}→{f.label.iloc[bi]}, "
                f"{f.step_rate.iloc[bi] * 100:.1f}%)을 보게 된 계기",
                f"{dim_col} 간 격차({gap:.1f}%p)를 확인하게 된 배경",
                f"표본 부족으로 판정을 미룬 항목({hidden_n}건)을 왜 지금 "
                f"함께 다루는지",
            ],
            "decide": ["실제 보고 대상", "실제 업무 목적",
                      "이번 보고서를 통해 결정하려는 사항"],
        },
        "6. 해석": {
            "suggest": [
                f"{dim_col} 간 격차가 {worst[dim_col]}({worst['전환율'] * 100:.1f}%)"
                f"~{best[dim_col]}({best['전환율'] * 100:.1f}%)로 벌어진다는 사실",
                f'반기 비교가 "{hc["verdict"]}"으로 판정된 것이 실패가 아니라 '
                f"정직한 결과라는 점",
                f"표본 부족으로 못 본 항목({hidden_n}건)이 앞으로 더 볼 가치가 "
                f"있는지",
            ],
            "decide": ["격차의 원인으로 무엇을 의심하는지(데이터로는 가릴 수 없다)",
                      "이 숫자가 실제 업무에서 무엇을 뜻하는지"],
        },
        "8. 제안": {
            "suggest": [
                f"격차가 큰 {dim_col}·항목에 대해 무엇을 할 것인지",
                "지금 하지 않을 것은 무엇이고 왜 미루는지",
            ],
            "decide": ["실제 조치 여부와 시점", "조치 우선순위"],
        },
    }


# ── 사람이 쓰는 장 (제공) ─────────────────────────────────────────
def _s2_background(human: dict) -> dict:
    return {
        "title": "2. 배경", "kind": "human",
        "body": human.get("2. 배경", ""),
        "placeholder": "이 분석을 왜 했는지, 어떤 의사결정을 앞두고 있는지 적으십시오.",
    }


def _s6_interpretation(human: dict) -> dict:
    return {
        "title": "6. 해석", "kind": "human",
        "body": human.get("6. 해석", ""),
        "placeholder": ("숫자가 무엇을 뜻하는지 적으십시오. "
                        "자동으로 쓰지 않습니다 — 해석은 사람의 책임입니다."),
    }


def _s8_proposal(human: dict) -> dict:
    return {
        "title": "8. 제안", "kind": "human",
        "body": human.get("8. 제안", ""),
        "placeholder": ("무엇을 할 것인지, 무엇을 하지 않을 것인지 적으십시오. "
                        "선택하지 않으면 제안이 아니라 보고입니다."),
    }


# ── 조립 ──────────────────────────────────────────────────────────
def _safe(title: str, fn, *args) -> dict:
    """아직 안 채운 장은 "todo" 종류로 돌려준다. 골격 전용."""
    from core.todo import NotYet
    try:
        return fn(*args)
    except NotYet as e:
        return {"title": title, "kind": "todo", "body": "", "todo": e}


def build(t: dict, human: dict | None = None,
          limit_rows: list[dict] | None = None) -> list[dict]:
    """8장을 조립한다. human 은 사람이 쓴 장의 본문 딕셔너리.
    limit_rows 를 주면 7장(한계)은 그 행들로 조립한다(실습 G의 편집 결과) —
    안 주면 s7_limit_rows() 로 매번 새로 조립한다.

    **순서와 자동/사람 구분은 바꾸지 않는다.** 장 개수는 도메인에 맞게 줄여도 되지만,
    해석과 제안을 자동으로 돌리는 것만은 하지 않는다.
    """
    human = human or {}
    return [
        _safe("1. 요약", _s1_summary, t),
        _s2_background(human),
        _safe("3. 방법", _s3_method, t),
        _safe("4. 결과", _s4_results, t),
        _safe("5. 실험", _s5_experiments, t),
        _s6_interpretation(human),
        _safe("7. 한계", _s7_limits, t, limit_rows),
        _s8_proposal(human),
    ]


def email_draft(t: dict, sections: list[dict]) -> dict:
    """이메일 초안. **실제로 보내지 않는다.**

    그대로 쓴다. 이메일 HTML은 인라인 스타일과 표 레이아웃만 쓴다 —
    외부 CSS·자바스크립트·이미지는 대부분의 메일 클라이언트가 막는다.

    받을 사람이 없으면 초안까지만 만들고, 게이트 3은 "보냈다고 치고" 기록만 남긴다.
    """
    summary = next((s["body"] for s in sections if s["title"].startswith("1.")), "")
    subject = f"[성장 리포트] {C.PERIOD[0][:7]}~{C.PERIOD[1][:7]}"
    html = (
        f'<div style="font-family:sans-serif;color:#0f172a;max-width:640px">'
        f'<h2 style="font-size:18px">{subject}</h2>'
        f'<p style="font-size:14px;line-height:1.7;white-space:pre-line">'
        f'{summary}</p>'
        f'<p style="font-size:12px;color:#64748b;margin-top:20px">'
        f'자동 생성 · {datetime.now().strftime("%Y-%m-%d %H:%M")}</p></div>')
    return {"to": C.EMAIL_TO_EXAMPLE, "subject": subject, "html": html}
