# -*- coding: utf-8 -*-
"""지표 계산.

**지표의 정의는 위키가 원본이다.** 이 파일은 위키에 적힌 정의를 코드로 옮긴 것일 뿐,
여기서 정의를 새로 만들지 않는다. 정의가 바뀌면 위키를 먼저 고친다.

────────────────────────────────────────────────────────────────────
★ 이 파일에는 통신사 컬럼명이 박혀 있다.

  billing_amount · is_churned · acquisition_channel · visitor_id ...

config.py 를 다 바꿔도 여기서 깨진다. **깨지는 것이 정상이다.**
컬럼명을 하나씩 내 것으로 맞추는 것이 이식 작업의 절반이다. → DESIGN.md §4-6
────────────────────────────────────────────────────────────────────

계산은 전부 pandas로 한다. 어디서 읽어왔든 입력은 동일한 DataFrame이다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats

from core import config as C
from core.load import to_dt
from core.todo import todo


# ── 퍼널 ──────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def funnel(fe: pd.DataFrame) -> pd.DataFrame:
    """단계별 도달 인원과 전환율.

    ★ Day2 실습 A에서 채웁니다.

    먼저 정할 것은 **그레인**이다.

        한 대상이 같은 단계를 두 번 밟을 수 있는가?
          있다 → 그냥 세면 안 된다. 고유값으로 센다 (nunique)
          없다 → 행을 그대로 세도 된다 (len)

    통신사 데이터에서는 한 사람이 여러 세션에 걸쳐 퍼널을 진행하므로
    세션 단위로 세면 전환율이 실제보다 **낮게** 나온다.

    반환: DataFrame[step, label, n, step_rate, cum_rate, drop, is_bottleneck]

        step           config.FUNNEL_STEPS 의 값
        label          config.FUNNEL_LABELS 의 값 (화면 표시용)
        n              그 단계에 도달한 수
        step_rate      전 단계 대비 비율 (첫 단계는 NaN)
        cum_rate       첫 단계 대비 비율
        drop           전 단계에서 빠진 수
        is_bottleneck  step_rate 가 가장 낮은 구간이면 True

    만들고 나서 **반드시 손계산과 대조한다.** 대조할 값이 없으면
    표본 100건을 눈으로 세어 비율을 낸다. 전수가 아니어도 자릿수는 잡힌다.

    그레인: 체크리스트 항목 1건(체크ID). 한 행이 같은 단계를 두 번 밟지 않으므로
    고유값 처리가 필요 없다 — 행을 그대로 센다.

    단계는 두 이진 플래그로 판정한다(7주차 토요일 실측):
        등록      전체 행
        완료      완료여부 == "Y"
        최종승인   최종승인 == "Y"
    """
    counts = {
        "등록": len(fe),
        "완료": int((fe["완료여부"] == "Y").sum()),
        "최종승인": int((fe["최종승인"] == "Y").sum()),
    }
    rows = []
    prev_n = None
    first_n = counts[C.FUNNEL_STEPS[0]]
    for step in C.FUNNEL_STEPS:
        n = counts[step]
        rows.append({
            "step": step,
            "label": C.FUNNEL_LABELS.get(step, step),
            "n": n,
            "step_rate": (n / prev_n) if prev_n else np.nan,
            "cum_rate": (n / first_n) if first_n else np.nan,
            "drop": (prev_n - n) if prev_n is not None else 0,
        })
        prev_n = n
    out = pd.DataFrame(rows)
    valid = out["step_rate"].dropna()
    out["is_bottleneck"] = (out["step_rate"] == valid.min()) if len(valid) else False
    return out


@st.cache_data(show_spinner=False)
def funnel_by(fe: pd.DataFrame, se: pd.DataFrame, dim: str,
              step_from: str, step_to: str) -> pd.DataFrame:
    """차원별 특정 구간 전환율. 평균 하나로는 어디를 고칠지 모른다.

    ★ Day3 실습 B에서 채웁니다.

    dim 은 분해 축이다. **무엇으로 쪼갤지는 내가 정한다.**
    기기·채널·지역·요금제·담당자·유입경로 — 도메인마다 다르다.

    쪼개는 기준은 이것이다: 그 축으로 나눴을 때 **손을 쓸 수 있는가.**
    나눠서 격차가 보여도 우리가 못 바꾸는 것이면 분해할 이유가 적다.

    반환: DataFrame[<dim>, 도달, 전환, 전환율, 비중]

    8주차 목요일 확정 — 완료여부/최종승인 두 플래그로 도달·전환을 판정한다
    (등록은 전체 행, 완료는 완료여부='Y', 최종승인은 최종승인='Y').
    두 번째 인자(se)는 이 도메인엔 테이블이 하나뿐이라 fe와 동일한 것을 받는다.
    """
    flag = {"등록": None, "완료": "완료여부", "최종승인": "최종승인"}
    base = fe if step_from == "등록" else fe[fe[flag[step_from]] == "Y"]
    reached = base if step_to == "등록" else base[base[flag[step_to]] == "Y"]

    n_base = base.groupby(dim, observed=True).size()
    n_reach = reached.groupby(dim, observed=True).size().reindex(n_base.index).fillna(0).astype(int)
    out = pd.DataFrame({"도달": n_base, "전환": n_reach}).reset_index()
    out["전환율"] = out["전환"] / out["도달"]
    out["비중"] = out["도달"] / out["도달"].sum()
    return out.sort_values("전환율")


# ── 유지 퍼널 ─────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def retention_funnel(t: dict) -> pd.DataFrame:
    """유지 퍼널. config.RETENTION_STEPS 의 단계대로 센다.

    ★ Day2 실습 D에서 채웁니다.

    획득 퍼널과 다른 점 셋:

        단계    주어지지 않는다. **내가 정의한다**
        방향    한 방향이 아니다. 오갈 수 있다
        시간    며칠이 아니라 몇 달~몇 년

    그래서 그레인이 다르다. 획득은 **대상 하나**지만 유지는 흔히 **대상 × 기간**이다.
    같은 오류의 두 얼굴이다 — 그레인을 잘못 잡으면 둘 다 틀린다.

    **퍼널이 아니면 퍼널이라고 부르지 않는다.** 세 가지를 물어라.

        이 단계는 앞 단계를 반드시 거치는가?  아니면 그냥 분류다
        그레인이 무엇인가?
        기간을 어떻게 자르는가?

    그리고 **관측 기간이 다른 대상을 누적값으로 비교하지 않는다.**
    비교하려면 비율(단위 기간당)로 바꾸거나, 같은 시점에 시작한 것끼리 묶는다.
    7주차 토요일에 겪은 생존 편향이 여기서 다시 나온다.

    반환: DataFrame[step, label, n, step_rate, cum_rate]

    8주차 화요일 확정 — 그레인: 계정과목(대상 하나, 대상×기간이 아니다).
    계정과목×회계기간별 최종승인율을 구해 50% 미만인 월을 "문제월"로 보고,
    그 최장 연속 개월수로 config.RETENTION_STEPS 3단계를 판정한다.
    """
    df = t[C.TABLES[0]]
    piv = df.assign(승인=(df["최종승인"] == "Y").astype(int))
    g = (piv.groupby(["계정과목", "회계기간"], observed=True)["승인"].mean()
         .reset_index().sort_values(["계정과목", "회계기간"]))

    max_streak: dict[str, int] = {}
    for acct, sub in g.groupby("계정과목", observed=True):
        streak = best = 0
        for ok in sub["승인"] >= 0.5:
            streak = 0 if ok else streak + 1
            best = max(best, streak)
        max_streak[str(acct)] = best

    thresholds = [1, 2, 3]
    ns = [sum(1 for v in max_streak.values() if v >= th) for th in thresholds]
    first_n = ns[0]
    rows, prev_n = [], None
    for (step, _cond), n in zip(C.RETENTION_STEPS, ns):
        rows.append({
            "step": step, "label": step, "n": n,
            "step_rate": (n / prev_n) if prev_n else np.nan,
            "cum_rate": (n / first_n) if first_n else np.nan,
        })
        prev_n = n
    return pd.DataFrame(rows)


# ── KPI ───────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def kpis(t: dict) -> dict:
    """지표 카드.

    ★ Day2 실습 E에서 채웁니다.

    ★ 아래 컬럼명은 전부 **통신사 것**이다. 내 데이터의 대응 컬럼으로 바꾼다.

        billing_amount  →  금액에 해당하는 컬럼
        is_churned      →  이탈 여부에 해당하는 컬럼

    없는 지표는 **빼면 된다.** 4개일 이유가 없다.

    반환: {"지표이름": {"value": float, "unit": str, "fmt": str}}
          fmt 은 화면 표시 형식이다. 예) "{:.2f}%"  "{:,.0f}원"

    예시 — 통신사:

        f = funnel(t["funnel_events"])
        return {
            "전환율": {"value": f.n.iloc[-1] / f.n.iloc[0] * 100,
                       "unit": "%", "fmt": "{:.2f}%"},
            "ARPU": {"value": float(t["usage_monthly"].billing_amount.mean()),
                     "unit": "원", "fmt": "{:,.0f}원"},
        }

    8주차 화요일 확정 — 규모·전환·속도·품질 네 축에서 하나씩:

        최종승인율(전환)  최종승인='Y' 건수 ÷ 전체 건수
        완료율(가드레일)  완료여부='Y' 건수 ÷ 전체 건수
        평균 지연일수(속도) 지연일수 컬럼 평균
        재작업률(품질)     검토횟수 >= 3 건수 ÷ 전체 건수
    """
    df = t[C.TABLES[0]]
    n = len(df)
    return {
        "최종승인율": {"value": (df["최종승인"] == "Y").mean() * 100,
                    "unit": "%", "fmt": "{:.1f}%"},
        "완료율": {"value": (df["완료여부"] == "Y").mean() * 100,
                 "unit": "%", "fmt": "{:.1f}%"},
        "평균 지연일수": {"value": float(df["지연일수"].mean()),
                     "unit": "일", "fmt": "{:.1f}일"},
        "재작업률": {"value": (df["검토횟수"] >= 3).mean() * 100,
                  "unit": "%", "fmt": "{:.1f}%"},
    }


@st.cache_data(show_spinner=False)
def monthly(t: dict) -> pd.DataFrame:
    """기간별 추이. 지표 카드의 스파크라인과 아카이브 비교에 쓴다.

    ★ Day2 실습 E에서 채웁니다. (kpis 와 함께)

    kpis() 가 돌려주는 지표 이름과 **열 이름이 대응**되어야 스파크라인이 그려진다.
    기간이 짧아 월별로 나눌 수 없으면 주별로 해도 되고, 아예 빼도 된다.

    반환: 인덱스가 기간(예 "2025-01"), 열이 지표인 DataFrame

    8주차 화요일 확정 — 회계기간(월) 그대로 사용. kpis()의 지표 이름과
    열 이름을 맞춘다.
    """
    df = t[C.TABLES[0]]
    g = df.groupby("회계기간", observed=True)
    out = pd.DataFrame({
        "최종승인율": g.apply(lambda x: (x["최종승인"] == "Y").mean() * 100,
                          include_groups=False),
        "완료율": g.apply(lambda x: (x["완료여부"] == "Y").mean() * 100,
                        include_groups=False),
        "평균 지연일수": g["지연일수"].mean(),
        "재작업률": g.apply(lambda x: (x["검토횟수"] >= 3).mean() * 100,
                        include_groups=False),
    })
    return out.sort_index()


def status_of(name: str, value: float) -> str:
    """지표 값을 상태 색으로 판정한다. 임계값은 config.THRESHOLDS 에 있다.

    이 함수는 **그대로 쓴다.** 판정 규칙이지 도메인이 아니다.
    THRESHOLDS 가 비어 있으면 전부 "ok"로 나온다 — 채우면 색이 갈린다.
    """
    th = C.THRESHOLDS.get(name)
    if not th:
        return "ok"
    # ★ 높을수록 나쁜 지표. 내 지표 이름을 넣는다.
    higher_is_worse = {"이탈률", "이탈율", "해지율", "불량률", "반품률",
                       "평균 지연일수", "재작업률"}
    if name in higher_is_worse:
        return ("block" if value > th["위험"]
                else "warn" if value > th["경고"] else "ok")
    return ("block" if value < th["위험"]
            else "warn" if value < th["경고"] else "ok")


# ── 실험 ──────────────────────────────────────────────────────────
# ★ 실험별로 어느 구간을 보는지. 도메인이 바뀌면 이 표를 갈아끼운다.
#   실험이 없는 도메인이면 비워 둔다.
EXP_STEPS: dict[str, tuple[str, str]] = {
    "EXP-001": ("랜딩방문", "요금제조회"),
    "EXP-002": ("요금제조회", "신청시작"),
    "EXP-003": ("신청시작", "신청완료"),
    "EXP-004": ("요금제조회", "신청시작"),
    "EXP-005": ("요금제조회", "신청시작"),
}


def _two_prop(sc, nc, stt, nt):
    """두 비율 비교. 차이·신뢰구간·p값을 함께 돌려준다.

    **그대로 쓴다.** 통계 계산은 도메인이 바뀌어도 같다.

    p값만 보면 '유의하지만 실질 효과가 없는' 경우를 놓친다.
    그래서 신뢰구간을 항상 함께 계산해 화면에 그린다.
    """
    rc, rt = sc / nc, stt / nt
    se = np.sqrt(rc * (1 - rc) / nc + rt * (1 - rt) / nt)
    if se == 0:
        return dict(rc=rc, rt=rt, nc=nc, nt=nt, diff=0, lo=0, hi=0, p=1.0, lift=0)
    z = (rt - rc) / se
    return dict(rc=rc, rt=rt, nc=nc, nt=nt, diff=rt - rc,
                lo=(rt - rc) - 1.96 * se, hi=(rt - rc) + 1.96 * se,
                p=2 * (1 - stats.norm.cdf(abs(z))),
                lift=(rt / rc - 1) if rc else 0)


def srm_check(asg: pd.DataFrame, exp_id: str) -> dict:
    """SRM(Sample Ratio Mismatch). 배정이 50:50인지 검정한다.

    **그대로 쓴다.** 7주차에 손으로 해본 그 계산이다.

    배정이 50:50이 아니면 배정 로직에 버그가 있다는 뜻이고,
    그 경우 어떤 효과가 나오든 해석할 수 없다.
    """
    a = asg[asg.experiment_id == exp_id]
    c = int((a.variant == "control").sum())
    t = int((a.variant == "treatment").sum())
    if c + t == 0:
        return {"ok": False, "c": 0, "t": 0, "p": 1.0, "ratio": (0.0, 0.0)}
    p = stats.chisquare([c, t]).pvalue
    return {"ok": p >= 0.001, "c": c, "t": t, "p": float(p),
            "ratio": (c / (c + t), t / (c + t))}


def trust_check(n_total: int, days_a: int | None = None,
                 days_b: int | None = None) -> str | None:
    """이 비교를 믿을 수 있는가. **계산하기 전에** 묻는다.

    ────────────────────────────────────────────────────────────
    오늘의 어려운 일은 계산이 아니다.
    **계산은 이미 할 수 있는데, 화면에 안 그리는 코드를 쓰는 것**이다.
    ────────────────────────────────────────────────────────────

    하나라도 걸리면 **사유 문자열**을 돌려준다. 돌려주면
    호출하는 쪽이 거기서 멈추고 **지표를 계산하지 않는다.**
    다 통과하면 None 을 돌려준다.

    "그래도 회색으로라도 보여주면 안 되나요?"

        안 됩니다. **사람은 본 숫자를 기억합니다.**
        옆에 아무리 경고를 붙여도 회의실에서 인용되는 것은 숫자입니다.

    8주차 목요일 확정 — 실험이 없는 도메인이라 배정 공정성(SRM) 대신
    표본과 비교 기간 길이만 본다. 못 믿을 조건 둘:

        표본이 30건 미만(config.MIN_SAMPLE)       → 계산은 되지만 값이 흔들린다
        비교하는 두 기간 길이가 20% 이상 다름      → 공정한 비교가 아니다

    반환: 못 믿을 이유(str) 또는 None
    """
    if n_total < C.MIN_SAMPLE:
        return f"표본 {n_total}건 (최소 {C.MIN_SAMPLE})"
    if days_a is not None and days_b is not None:
        longer, shorter = max(days_a, days_b), min(days_a, days_b)
        if shorter == 0 or (longer - shorter) / longer >= 0.2:
            return f"비교 기간 길이 불일치 ({days_a}일 vs {days_b}일)"
    return None


@st.cache_data(show_spinner=False)
def half_year_comparison(t: dict) -> dict:
    """반기 전후 비교 판정 카드. 실험이 없는 도메인이라 이것이 실험 카드를 대신한다.

    8주차 목요일 확정 — 주지표: 최종승인율, 가드레일: 완료율.
    판정 순서(1부 판단 기준 그대로): 못 믿을 조건 → 주지표 → 가드레일.

        믿을 수 없다                        → "무효" (계산하지 않는다)
        주지표 변화 5%p 미만                → "효과 없음"
        가드레일(완료율) 2%p 이상 나빠짐     → "주의 필요"
        주지표가 나빠지는 쪽으로 5%p 이상    → "악화"
        그 외(개선 + 가드레일 이상 없음)     → "성공"

    이 비교는 인과를 주장할 수 없다. 무작위 배정이 없었으므로 다른 요인의
    영향을 배제하지 못한다 — 카드 문구에 반드시 포함한다.
    """
    df = t[C.TABLES[0]]
    period = df["회계기간"].astype(str)
    is_h1 = period <= "2026-06"
    h1, h2 = df[is_h1], df[~is_h1]
    n1, n2 = len(h1), len(h2)

    days_a = (pd.Timestamp("2026-06-30") - pd.Timestamp("2026-01-01")).days
    days_b = (pd.Timestamp("2026-12-31") - pd.Timestamp("2026-07-01")).days
    row = {"primary": "최종승인율", "guardrail": "완료율",
           "period_a": "2026 상반기", "period_b": "2026 하반기",
           "n1": n1, "n2": n2, "days_a": days_a, "days_b": days_b}

    reason = trust_check(min(n1, n2), days_a, days_b)
    if reason:
        row.update(verdict="무효", color="block", reason=reason)
        return row

    r1, r2 = (h1["최종승인"] == "Y").mean() * 100, (h2["최종승인"] == "Y").mean() * 100
    g1, g2 = (h1["완료여부"] == "Y").mean() * 100, (h2["완료여부"] == "Y").mean() * 100
    delta, g_delta = r2 - r1, g2 - g1
    row.update(r1=r1, r2=r2, delta=delta, g1=g1, g2=g2, g_delta=g_delta)

    if abs(delta) < 5:
        row.update(verdict="효과 없음", color="none",
                    reason="주지표 변화가 5%p 미만입니다")
    elif g_delta <= -2:
        row.update(verdict="주의 필요", color="warn",
                    reason="주지표는 움직였으나 가드레일(완료율)이 나빠졌습니다")
    elif delta < 0:
        row.update(verdict="악화", color="block", reason="")
    else:
        row.update(verdict="성공", color="ok", reason="")
    return row


@st.cache_data(show_spinner=False)
def experiment_results(t: dict) -> list[dict]:
    """실험 결과와 판정.

    **판정 순서가 이 함수의 전부다.** 믿을 수 있는지 먼저 묻고,
    믿을 수 있을 때만 계산한다.

    좋은 결과를 먼저 보면 경고를 무시하고 싶어진다. 그래서 사람의 규율에
    맡기지 않고 **코드로 순서를 박는다.**

    실험이 없는 도메인이면 이 함수는 빈 목록을 돌려준다. 대신 전후 비교
    카드를 만들되 **"인과 주장 불가"를 카드에 박아 둔다.** → DESIGN.md §4-4
    """
    if "experiments" not in t or "experiment_assignments" not in t:
        return []
    ex, asg, fe = t["experiments"], t["experiment_assignments"], t["funnel_events"]
    reach = {s: set(fe.loc[fe.funnel_step == s, "visitor_id"]) for s in C.FUNNEL_STEPS}
    out = []
    for _, e in ex.iterrows():
        eid = e.experiment_id
        srm = srm_check(asg, eid)
        n_total = int((asg.experiment_id == eid).sum())
        row = {
            "id": eid, "name": e.experiment_name, "hypothesis": e.hypothesis,
            "primary": e.primary_metric, "guardrail": e.guardrail_metric,
            "start": e.start_date, "end": e.end_date, "srm": srm,
        }

        # ★ 판정이 계산보다 먼저다. 못 믿으면 여기서 끝난다.
        reason = trust_check(srm, n_total)
        if reason:
            row["verdict"] = "무효"
            row["color"] = "block"
            row["reason"] = reason
            out.append(row)
            continue        # 지표를 계산하지 않는다. 숨기는 것이 아니다.

        # ── 여기부터 계산 ─────────────────────────────────────────
        if eid not in EXP_STEPS:
            row.update(verdict="데이터 없음", color="none",
                       reason="EXP_STEPS 에 이 실험의 구간이 없습니다.")
            out.append(row)
            continue
        sf, stp = EXP_STEPS[eid]
        a = asg[asg.experiment_id == eid][["visitor_id", "variant", "assigned_at"]]
        a = a[a.visitor_id.isin(reach[sf])]
        a = a.assign(conv=a.visitor_id.isin(reach[stp]).astype(int))
        g = a.groupby("variant", observed=True).conv.agg(["sum", "count"])
        if len(g) < 2:
            row.update(verdict="데이터 없음", color="none")
            out.append(row)
            continue
        r = _two_prop(g.loc["control", "sum"], g.loc["control", "count"],
                      g.loc["treatment", "sum"], g.loc["treatment", "count"])
        row.update(r, step_from=sf, step_to=stp, assignments=a)

        # 가드레일 — 주지표를 올리려 할 때 희생될 수 있는 것
        # ★ 아래는 통신사 컬럼(is_churned)이다. 내 가드레일 지표로 바꾼다.
        row["guard"] = None
        if "유지율" in str(e.guardrail_metric) and "customers" in t:
            cu = t["customers"]
            m = cu.merge(a[["visitor_id", "variant"]], on="visitor_id", how="inner")
            if len(m) and m.variant.nunique() == 2:
                ret = m.groupby("variant", observed=True).is_churned.mean()
                row["guard"] = {
                    "name": e.guardrail_metric,
                    "control": float(1 - ret["control"]),
                    "treatment": float(1 - ret["treatment"]),
                    "delta": float((1 - ret["treatment"]) - (1 - ret["control"])),
                }

        # 판정 — ★ 3%p 는 예시다. 내 가드레일 기준으로 바꾼다.
        sig = r["p"] < 0.05
        guard_bad = row["guard"] is not None and row["guard"]["delta"] < -0.03
        if guard_bad:
            # 주지표가 좋아져도 가드레일이 무너지면 성공이 아니다
            row.update(verdict="주의 필요", color="warn",
                       reason="주지표는 개선됐으나 가드레일이 악화됐습니다.")
        elif sig and r["lift"] > 0:
            row.update(verdict="성공", color="ok", reason="")
        elif sig:
            row.update(verdict="악화", color="block", reason="")
        else:
            row.update(verdict="효과 없음", color="none",
                       reason="통계적으로 유의한 차이가 없습니다.")
        out.append(row)
    return out


def peeking_curve(res: dict, start: str, cuts=(7, 14, 30, 60, 92)) -> pd.DataFrame:
    """관측 시점별 누적 결과. '그때 멈췄다면 무엇을 봤을까'를 재현한다.

    **그대로 쓴다.** 7주차에 겪은 조기 중단이다.
    """
    a = res.get("assignments")
    if a is None:
        return pd.DataFrame()
    a = a.copy()
    a["d"] = (to_dt(a.assigned_at) - pd.Timestamp(start)).dt.days
    rows = []
    for c in cuts:
        s = a[a.d <= c].groupby("variant", observed=True).conv.agg(["sum", "count"])
        if len(s) < 2 or s["count"].min() < 30:
            continue
        r = _two_prop(s.loc["control", "sum"], s.loc["control", "count"],
                      s.loc["treatment", "sum"], s.loc["treatment", "count"])
        rows.append({"cut": c, "lift": r["lift"], "p": r["p"], "sig": r["p"] < 0.05})
    return pd.DataFrame(rows)


def weekly_effect(res: dict, start: str, bucket_days: int = 14) -> pd.DataFrame:
    """기간을 쪼개 효과 추이를 본다. 신규성 효과는 전체 평균에 가려진다.

    **그대로 쓴다.** 7주차에 겪은 그것이다.
    """
    a = res.get("assignments")
    if a is None:
        return pd.DataFrame()
    a = a.copy()
    a["b"] = (to_dt(a.assigned_at) - pd.Timestamp(start)).dt.days // bucket_days
    g = (a[a.b >= 0].groupby(["b", "variant"], observed=True).conv
         .mean().unstack().dropna())
    if g.empty:
        return pd.DataFrame()
    g["lift"] = g.treatment / g.control - 1
    g = g.reset_index()
    g["label"] = g.b.apply(lambda i: f"{int(i)*2+1}~{int(i)*2+2}주")
    return g


# ── 채널 효율 (선택 과제) ─────────────────────────────────────────
@st.cache_data(show_spinner=False)
def channel_efficiency(t: dict) -> pd.DataFrame:
    """비용만 보면 순위가 뒤집힌다. 유지율까지 반영한 유효 비용을 함께 낸다.

    ★ Day3 선택 과제입니다. 안 만들어도 나머지가 돕니다.

    획득 비용이 싼 경로가 실제로 싼 것이 아니다 —
    데려온 대상이 남지 않으면 같은 자리를 다시 채워야 한다.

        유효 비용 = 획득 비용 / 유지율

    비용 개념이 없으면 **투입 공수(인시)**로 해도 된다.
    획득 경로 구분이 없으면 이 함수를 지운다.

    ★ 여기 쓰이는 CHANNEL_CAC 는 **가정값**이다. 광고비 실측 테이블에서
      유도하지 않는다 — 광고비는 개인 단위로 추적되지 않아 가입과 이을 수 없다.
      리포트에 이 값이 들어가면 "가정값 기반"을 문장에 남긴다. → DESIGN.md §4-3

    반환: DataFrame[채널, 방문, 가입, 전환율, CAC, 유지율, 유효CAC, 역전]
    """
    todo("Day3 선택 과제", "채널 효율",
         "내 도메인에 획득 경로 구분이 있습니까? 비용이 없으면 투입 공수로 바꾸십시오.",
         "core/metrics.py  channel_efficiency()")
