"""평생 사주의 성향 문단을 삶의 흐름으로 쓴다.

성격운세의 문장을 그대로 옮기지 않는다. 원문에 표지가 있는 특성만 골라,
그 특성이 나이와 삶의 과제에 어떻게 이어지는지로 다시 쓴다.
시기별 문장은 이 사람의 실제 대운 나이에서 나오고, 십신 이름은 넣지 않는다.
"""
from domains.personality.trait_signals import matched, shares

_NATURE_KEYS = ("base_nature", "strengths", "relationships", "work_style")
_CAUTION_KEYS = ("weaknesses", "supplement")

_PATH = {
    "재성": "{a}세부터 {b}세까지는 들어온 결과와 자산이 그다음 삶의 폭을 정합니다.",
    "관성": "{a}세부터 {b}세까지는 맡은 자리와 책임이 이름과 신뢰를 만듭니다.",
    "인성": "{a}세부터 {b}세까지는 배움과 사람의 도움이 다음 판단을 준비합니다.",
    "비겁": "{a}세부터 {b}세까지는 동료와 나의 몫을 나누는 방식이 자리를 만듭니다.",
    "식상": "{a}세부터 {b}세까지는 만들어 낸 결과물이 다음 활동의 근거가 됩니다.",
}
_PATH_UNKNOWN = "{a}세부터 {b}세까지는 그 시기의 과제가 다음 10년의 조건을 바꿉니다."

# 20세 미만은 학업·용돈·교우·가정만 말한다. 성인 문장을 이 구간에 쓰지 않는다.
_PATH_YOUTH = {
    "재성": "{a}세부터 {b}세까지는 용돈과 살림을 가까이서 보며 아껴 쓰는 감각을 익히는 시기입니다.",
    "관성": "{a}세부터 {b}세까지는 규칙과 기대 안에서 자기 역할을 배우는 시기입니다.",
    "인성": "{a}세부터 {b}세까지는 배움과 돌봄 속에서 기초를 쌓는 시기입니다.",
    "비겁": "{a}세부터 {b}세까지는 친구와 형제 사이에서 내 몫과 같이하는 법을 익히는 시기입니다.",
    "식상": "{a}세부터 {b}세까지는 호기심과 표현을 공부와 놀이로 시험하는 시기입니다.",
}
_PATH_BRIDGE = {
    "재성": "{a}세부터 19세까지는 용돈과 살림의 감각을 익히고, 20세 전후에 그 감각이 스스로 책임지는 생활의 기준으로 넘어갑니다.",
    "관성": "{a}세부터 19세까지는 규칙과 기대를 배우고, 20세 전후에 그 역할이 스스로 맡는 자리의 기준으로 넘어갑니다.",
    "인성": "{a}세부터 19세까지는 배움과 돌봄 속에서 기초를 쌓고, 20세 전후에 그 공부가 스스로 판단하는 기준으로 넘어갑니다.",
    "비겁": "{a}세부터 19세까지는 친구 사이에서 내 몫을 배우고, 20세 전후에 그 경험이 함께 일하는 방식으로 넘어갑니다.",
    "식상": "{a}세부터 19세까지는 호기심과 표현을 공부와 놀이로 시험하고, 20세 전후에 그 표현이 직접 만드는 역할로 넘어갑니다.",
}
_PATH_TRANSITION = {
    "재성": "{a}세부터 {b}세까지는 22세 전후를 기점으로, 학업과 용돈의 감각이 스스로 버는 결과의 기준으로 넘어가는 시기입니다.",
    "관성": "{a}세부터 {b}세까지는 22세 전후를 기점으로, 규칙을 지키던 습관이 스스로 맡는 역할로 넘어가는 시기입니다.",
    "인성": "{a}세부터 {b}세까지는 22세 전후를 기점으로, 배우던 내용이 스스로 판단하는 기준으로 넘어가는 시기입니다.",
    "비겁": "{a}세부터 {b}세까지는 22세 전후를 기점으로, 친구 사이의 몫이 함께 일하는 방식으로 넘어가는 시기입니다.",
    "식상": "{a}세부터 {b}세까지는 22세 전후를 기점으로, 표현과 공부가 직접 만들어 내는 역할로 넘어가는 시기입니다.",
}

_DIRECTION = (
    "이 흐름에서 성향은 능력의 이름이 아니라, 각 시기의 과제를 대하는 태도로 쓰입니다. "
    "앞 시기에 통한 방식을 다음 시기에도 자동으로 가져가면, 과제는 바뀌었는데 성과의 종류만 예전 것에 머물게 됩니다. "
    "25세 이후의 돈은 그 시기에 손에 남는 기준으로 다음 생활의 크기가 되고, 일은 그 시기에 지킨 역할로 다음 이름이 됩니다. "
    "관계도 같습니다. 그 10년에 함께 결과를 낸 사람이 이후의 협력으로 남습니다. "
    "인생 전반에 유리한 태도는 시기가 시작되는 나이마다 이번 10년의 중심 과제를 한 줄로 적고, 일의 폭과 돈의 쓰임과 만날 사람을 그 줄에 맞추는 것입니다."
)

_ENTER = {
    "재성": "{age}세부터는 돈과 실적이 앞 시기의 속도와 다른 조건을 만듭니다. {age}세에 손에 남는 것을 만들지 못하면, 그 뒤의 생활 크기가 기대보다 작아집니다.",
    "관성": "{age}세부터는 맡은 역할과 공적인 신뢰가 삶의 조건을 바꿉니다. {age}세에 직전 시기의 속도를 그대로 유지하면, 자리는 와도 그 나이 이후에 지키지 못합니다.",
    "인성": "{age}세부터는 배움과 사람의 도움이 다음 실력의 재료가 됩니다. {age}세에 직함만 지키느라 공부를 미루면, 그다음 시기에 꺼낼 전문성이 비어 있습니다.",
    "비겁": "{age}세부터는 동료와 몫을 나누는 방식이 일의 주인이 됩니다. {age}세에도 혼자 결정하던 습관을 그대로 두면, 함께 여는 판에서 사람이 먼저 떠납니다.",
    "식상": "{age}세부터는 만들어 낸 결과물이 이름과 기회의 근거가 됩니다. {age}세에 상의만 늘리고 끝까지 내놓지 않으면, 그 10년은 바쁘기만 하고 남지 않습니다.",
}
_ENTER_UNKNOWN = "{age}세부터는 직전 10년의 방식이 그대로 통하지 않습니다. 과제가 바뀌었는데 속도만 예전 것을 쓰면, 바쁜 해만 남고 결과는 비기 쉽습니다."
_ENTER_YOUTH = {
    "재성": "{age}세부터는 집안의 살림과 용돈을 가까이서 보게 됩니다. 이 나이에는 돈의 크기보다, 아껴 쓰는 감각을 익히는 편이 이후의 생활 기준이 됩니다.",
    "관성": "{age}세부터는 규칙과 기대가 일상의 조건이 됩니다. 역할을 배우는 일과, 규칙을 견디기만 하는 일은 이 나이에서 이미 갈립니다.",
    "인성": "{age}세부터는 배움과 돌봄이 하루의 중심이 됩니다. 공부를 미루면 성적보다, 나중에 스스로 판단할 재료가 비기 쉽습니다.",
    "비겁": "{age}세부터는 친구와 형제 사이에서 내 몫이 분명해집니다. 같이하는 법을 익히지 않으면, 잘해도 함께 남는 친구가 줄어듭니다.",
    "식상": "{age}세부터는 호기심과 표현을 공부와 놀이로 시험하게 됩니다. 보여 주기만 하고 끝까지 해 보지 않으면, 흥미는 많고 남은 결과는 적습니다.",
}
_ENTER_EARLY = {
    "재성": "{age}세부터는 22세 전후를 기점으로 용돈의 감각이 스스로 책임지는 생활로 넘어갑니다. 이 구간에서 손에 남는 기준을 정하지 않으면, 이후의 생활 크기가 들쑥날쑥해집니다.",
    "관성": "{age}세부터는 22세 전후를 기점으로 규칙이 스스로 맡는 역할로 바뀝니다. 속도를 역할에 맞게 조절하지 않으면, 자리는 와도 오래 지키지 못합니다.",
    "인성": "{age}세부터는 22세 전후를 기점으로 배우던 내용이 스스로의 판단이 됩니다. 이 구간의 공부를 미루면, 다음 시기에 꺼낼 이해가 비어 있습니다.",
    "비겁": "{age}세부터는 22세 전후를 기점으로 친구 사이의 몫이 함께 일하는 방식으로 바뀝니다. 혼자 정하던 습관을 그대로 두면, 같이 여는 일에서 사람이 먼저 떠납니다.",
    "식상": "{age}세부터는 22세 전후를 기점으로 표현이 직접 만드는 역할이 됩니다. 상의만 늘리고 끝까지 내놓지 않으면, 이 구간은 바쁘기만 하고 남지 않습니다.",
}
_RUN_PREFERENCE = {
    "vision": ("식상", "인성"),
    "autonomy": ("관성", "인성"),
    "lead": ("비겁", "관성"),
    "drive": ("재성", "식상"),
    "finish": ("식상", "재성"),
    "scatter": ("식상", "비겁"),
    "blunt": ("비겁", "관성"),
    "heat": ("재성", "식상"),
}

_STEADY = (
    "{a}세부터 {b}세까지 같은 과제가 길게 이어집니다. "
    "익숙해진 방식이 곧 맹점이 되어, 깊이는 쌓이는데 다른 선택지를 시험하지 않기 쉽습니다. "
    "돈은 같은 기준으로만 모으게 되고, 일은 같은 역할에만 머물며, 관계는 이미 편한 사람으로만 좁아집니다. "
    "잘 되던 해가 막히는 해에도 방법을 바꾸지 않으면, 들인 시간에 비해 이후의 폭이 커지지 않습니다. "
    "경계할 점은 성향을 탓하기 전에, 이 긴 구간 안에서 돈과 일과 관계의 기준을 한 번씩 다시 적어 보는 것입니다."
)

_NATURE = {
    "vision": (
        "보는 범위가 넓은 특성은 {a}세부터 {b}세 사이에 활동 무대가 차례로 넓어지는 방식으로 나타납니다. "
        "이 구간에 한 분야의 깊이를 먼저 쌓아 두면, 그다음 시기의 자리가 그 깊이 위에서 넓어집니다. "
        "구상만 앞서고 손에 남는 실력이 없으면, 시기가 바뀌는 나이마다 일을 처음부터 다시 깔게 됩니다. "
        "이 구간에 유리한 선택은 영역을 늘리기 전에, 사람들이 찾아오는 실력을 하나 고정해 두는 것입니다."
    ),
    "autonomy": (
        "권한을 스스로 쥐는 환경에서 능력이 오래 갑니다. "
        "{a}세부터 {b}세 사이에 방법까지 잠그는 자리에 들어가면, 성과가 나도 그 역할을 오래 지키지 못해 경력의 줄기가 끊기기 쉽습니다. "
        "그다음 시기의 위치는 그 전에 이어 온 경력의 길이에서 정해지는 경우가 많습니다. "
        "이 구간을 가르는 선택은 자유 그 자체보다, 결과는 묻되 방법은 맡기는 자리를 고르는 것입니다."
    ),
    "lead": (
        "사람이 따르는 힘은 {a}세부터 {b}세의 협력과 역할로 남습니다. "
        "이 구간에 함께 일하는 범위가 넓어지고, 그다음 시기에는 그 관계가 신뢰와 기회로 돌아옵니다. "
        "사람만 많고 맡은 역할이 없으면 인연은 늘어도 사회적 위치는 쌓이지 않습니다. "
        "유리한 태도는 모임을 여는 것보다, 한 계절 이상 같이 결과를 내는 관계를 남기는 것입니다."
    ),
    "drive": (
        "결정을 미루지 않는 특성은 {a}세부터 {b}세의 갈림길에서 시기를 놓치지 않게 해 줍니다. "
        "이 구간의 선택이 이후 10년의 일과 자산 크기를 정합니다. "
        "다만 그 속도를 모든 결정에 쓰면, 돌이키는 비용이 다음 시기의 자산을 잠식합니다. "
        "필요한 태도는 방향은 빨리 정하되, 돈과 자리처럼 되돌리기 어려운 것만 하룻밤 더 보는 것입니다."
    ),
}

_CAUTION = {
    "finish": (
        "긴 목표를 실현하는 데 필요한 태도는 시작의 크기보다 마지막 구간의 주인입니다. "
        "{a}세부터 {b}세까지 열어 둔 일이 그다음 시기의 자산과 이름으로 남으려면, 끝 구간을 다른 사람에게만 넘기지 않아야 합니다. "
        "끝을 넘기지 못한 일은 경력에서 성과로 집계되지 않고, 그 공백이 다음 시기의 신뢰를 낮춥니다. "
        "인생 전반에서 유의할 점은 판을 늘리기 전에, 이미 연 일의 완료 기준을 먼저 채우는 것입니다."
    ),
    "scatter": (
        "여러 판을 동시에 열어 두는 특성은 인생에서 성과가 흩어지는 비용이 됩니다. "
        "{a}세부터 {b}세 사이에 이름과 돈이 한 줄기로 모이지 않으면, 그다음 시기의 자산도 조각으로 남기 쉽습니다. "
        "각각의 일은 시작 기록만 있고 완료가 없으면, 바빴던 10년이 다음 시기의 신뢰로 환산되지 않습니다. "
        "유의할 점은 새 일을 더하기 전에, 이미 연 일 가운데 하나만이라도 끝까지 닫는 것입니다."
    ),
    "autonomy": (
        "통제가 답답해 자리를 떠나는 선택은 한 번의 해방처럼 보여도, 경력에서는 줄기가 끊기는 비용이 됩니다. "
        "{a}세부터 {b}세 사이에 방법까지 정하는 역할이 오면 떠나고 싶은 마음이 커지기 쉽습니다. "
        "그때마다 판을 접으면 그다음 시기의 위치는 짧은 경력의 합으로 남습니다. "
        "인생에서 필요한 태도는 자리를 버리기 전에, 내가 정할 수 있는 범위와 상대가 정할 범위를 나눠 한 번은 제안해 보는 것입니다."
    ),
    "blunt": (
        "할 말을 바로 두는 특성은 인생의 중요한 선택에서는 시간을 아끼게 해 줍니다. "
        "다만 사람과의 협력에서는 내용이 맞아도 관계가 먼저 식을 수 있습니다. "
        "{a}세부터 {b}세 사이에 함께 일하는 범위가 넓어질 때 이 차이가 커지고, 그다음 시기의 신뢰는 그때 남은 관계에서 나옵니다. "
        "인생을 가를 태도는 결론의 속도는 유지하되, 오래 갈 사람과는 상대가 들은 점을 확인한 뒤에 결정을 알리는 것입니다."
    ),
    "heat": (
        "마음이 오른 날의 결정이 인생의 방향을 빨리 트는 힘이 됩니다. "
        "열이 가라앉은 뒤에 실행이 따라가지 않으면, {a}세부터 {b}세 사이에 연 약속이 그다음 시기의 부담과 끊긴 경력으로 남습니다. "
        "큰 지출이나 동업처럼 되돌리기 어려운 선택은 뜨거운 날에 확정하지 않는 편이 이후 10년을 지킵니다. "
        "유의할 점은 방향은 그 날 적되, 실행은 다음 날 같은 시각에 다시 읽고 나서 하는 것입니다."
    ),
    "vision": (
        "그림이 큰 특성은 {a}세부터 {b}세에 활동 범위를 넓히는 힘이 됩니다. "
        "이 구간에 깊이를 남기지 않으면, 범위만 넓고 사람들이 찾는 실력은 다음 시기로 넘어가지 않습니다. "
        "유의할 점은 판을 키우기 전에, 한 분야에서 다시 찾는 결과를 하나 만드는 것입니다. "
        "결과물이 없는 확장은 바빠 보여도 이후의 신뢰를 만들지 못합니다."
    ),
    "drive": (
        "빠른 결정은 갈림길의 시기를 잡아 주지만, 모든 선택에 같은 속도를 쓰면 되돌리는 비용이 커집니다. "
        "{a}세부터 {b}세 사이에 잠근 돈과 자리가 그다음 시기의 선택지를 미리 좁힐 수 있습니다. "
        "인생에서 경계할 점은 방향은 빨리 정하되, 자산과 역할처럼 오래 남는 약속은 하루를 더 보고 확정하는 것입니다. "
        "그 하루가 없으면 빠른 장점이 다음 10년의 수리 비용으로 바뀝니다."
    ),
    "lead": (
        "사람이 모이는 힘은 사회적 자리를 만들지만, 역할이 없는 모임은 인연만 늘리고 신뢰는 남기지 않습니다. "
        "{a}세부터 {b}세 사이에 관계의 폭이 넓어질 때 함께 낸 결과가 있어야 그다음 시기의 협력으로 이어집니다. "
        "경계할 점은 사람을 모으는 횟수보다, 한 계절 이상 같은 결과를 만든 관계가 몇인지 보는 것입니다. "
        "그 수가 비어 있으면 말년의 네트워크도 이름만 남기 쉽습니다."
    ),
}


def build_core_voice(character, stages, facts):
    """(personality, weaknesses). 성격 원문과 같은 문장을 넣지 않는다."""
    steps = _steps(stages, facts)
    runs = _runs(steps)
    nature_names = matched(_blob(character, _NATURE_KEYS))
    caution_names = matched(_blob(character, _CAUTION_KEYS))
    nature_src = _blob(character, _NATURE_KEYS)
    caution_src = _blob(character, _CAUTION_KEYS)
    source = f"{nature_src}\n{caution_src}"
    nature_assigned = _assign_runs(nature_names, runs)
    caution_assigned = _assign_runs(caution_names, runs)

    personality_parts = [_nature_paragraph(name, nature_assigned.get(name)) for name in nature_names]
    personality_parts.append(_path_paragraph(runs))
    weaknesses_parts = [_caution_paragraph(name, caution_assigned.get(name)) for name in caution_names]
    weaknesses_parts.append(_caution_timing(runs))

    return (
        _keep(personality_parts, source),
        _keep(weaknesses_parts, source),
    )


def _blob(character, keys):
    if not isinstance(character, dict):
        return ""
    return " ".join(str(character.get(key) or "") for key in keys)


def _steps(stages, facts):
    rows = []
    for stage, fact in zip(stages or [], facts or []):
        ages = (stage or {}).get("age_range") or []
        if len(ages) != 2:
            continue
        group = ""
        if isinstance(fact, dict):
            group = fact.get("sipsin_group") or ""
        rows.append({"start": int(ages[0]), "end": int(ages[1]), "group": group})
    return rows


def _runs(steps):
    runs = []
    for step in steps:
        if runs and runs[-1]["group"] == step["group"]:
            runs[-1]["end"] = step["end"]
        else:
            runs.append(dict(step))
    return runs


def _band(run):
    """20세 미만은 학업·용돈·교우·가정만, 20세 전후는 과도기, 25세부터 성인 문장."""
    if run["end"] < 20:
        return "youth"
    if run["start"] < 20:
        return "bridge"
    if run["start"] < 25:
        return "transition"
    return "adult"


def _adult_window(run):
    """특성 문장의 경력·자산 표현은 25세 이후에만 붙인다."""
    if run["start"] < 25 <= run["end"]:
        return {"start": 25, "end": run["end"], "group": run["group"]}
    return run


def _nature_paragraph(name, run):
    template = _NATURE.get(name)
    if not template or not run:
        return ""
    window = _adult_window(run)
    return template.format(a=window["start"], b=window["end"])


def _caution_paragraph(name, run):
    template = _CAUTION.get(name)
    if not template or not run:
        return ""
    window = _adult_window(run)
    return template.format(a=window["start"], b=window["end"])


def _path_paragraph(runs):
    if not runs:
        return _DIRECTION
    bits = [_path_sentence(run) for run in runs]
    return " ".join(bits) + " " + _DIRECTION


def _path_sentence(run):
    band = _band(run)
    table = {
        "youth": _PATH_YOUTH,
        "bridge": _PATH_BRIDGE,
        "transition": _PATH_TRANSITION,
        "adult": _PATH,
    }[band]
    sentence = table.get(run["group"], _PATH_UNKNOWN).format(a=run["start"], b=run["end"])
    if band == "bridge" and run["end"] >= 25:
        adult = _PATH.get(run["group"], _PATH_UNKNOWN).format(a=25, b=run["end"])
        sentence = f"{sentence} {adult}"
    return sentence


def _caution_timing(runs):
    if not runs:
        return _STEADY.format(a=25, b=34)
    if len(runs) == 1:
        run = runs[0]
        if run["end"] < 25:
            return _ENTER_YOUTH.get(run["group"], _ENTER_UNKNOWN).format(age=run["start"])
        return _STEADY.format(a=max(run["start"], 25), b=run["end"])
    return " ".join(_enter_sentence(run) for run in runs[1:])


def _enter_sentence(run):
    band = _band(run)
    if band == "adult":
        table = _ENTER
    elif band == "transition":
        table = _ENTER_EARLY
    else:
        table = _ENTER_YOUTH
    return table.get(run["group"], _ENTER_UNKNOWN).format(age=run["start"])


def _assign_runs(names, runs):
    """성인 구간에 특성을 나누어 붙인다. 20세 미만에는 경력 문장을 싣지 않는다."""
    pool = [run for run in runs if run["end"] >= 25 and run["start"] >= 20] or [run for run in runs if run["end"] >= 25] or list(runs)
    if not pool:
        return {}
    used = set()
    assigned = {}
    for name in names:
        preferred = _RUN_PREFERENCE.get(name, ())
        choice = None
        for run in pool:
            if run["group"] in preferred and run["start"] not in used:
                choice = run
                break
        if choice is None:
            for run in pool:
                if run["start"] not in used:
                    choice = run
                    break
        if choice is None:
            choice = pool[len(assigned) % len(pool)]
        used.add(choice["start"])
        assigned[name] = choice
    return assigned


def _keep(parts, source):
    kept = []
    for part in parts:
        text = (part or "").strip()
        if not text or shares(text, source):
            continue
        if any(shares(text, previous) for previous in kept):
            continue
        kept.append(text)
    return "\n\n".join(kept)
