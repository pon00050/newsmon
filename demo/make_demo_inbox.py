#!/usr/bin/env python3
"""Write SYNTHETIC (entirely fictional) plain-text wire items for the Newsmon public demo.

Usage:  python demo/make_demo_inbox.py --out DIR [--now ISO8601]

Every item is fixed in this file, so output is deterministic for a given --now. Timestamps are spread over the 48 hours
before --now (default: current UTC time). Format: tests/fixtures/wire/plain/FORMAT.md. Stdlib only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

MARK = "[SYNTHETIC DEMO]"
TZ = {
    "en": timezone(timedelta(hours=-5)),
    "ko": timezone(timedelta(hours=9)),
    "zh": timezone(timedelta(hours=8)),
}
FOOTER = {
    "en": "{m} Source: {a}. All names and events are fictional.",
    "ko": "{m} 출처: {a}. 모든 인물과 사건은 가상이다.",
    "zh": "{m} 来源：{a}。所有人物与事件均为虚构。",
}


def I(lang, urg, slug, head, place, desc, text, agency, new=True, ver=1, off=None):
    """One item. new=False means the same story as the previous item (exact copy or version update)."""
    return dict(lang=lang, urg=urg, slug=slug, head=head, place=place, desc=desc, text=text, agency=agency,
                new=new, ver=ver, off=off)


# Order matters only for the generated offsets and file names. 48 files: 24 EN, 14 KO, 10 ZH.
ITEMS = [
    # --- English ----------------------------------------------------------------------------------------------------
    I("en", 2, "PORT-TW-STORM", "FLASH: Port authority halts container traffic near Taiwan Strait after storm",
      "MERIDIAN, Aldoria", "Storm forces pause in container handling",
      "Port authority officials suspended container handling on Monday after a storm moved through the approaches to the "
      "Taiwan Strait. Operations are expected to resume once wind readings fall below the set threshold.", "Demo Wire"),
    I("en", 2, "STEEL-TARIFF-FLASH", "FLASH: Harbor authority announces emergency review of tariff on imported steel",
      "BRIGHTWATER, Aldoria", "Emergency review of steel tariff schedule",
      "The Brightwater harbor authority said on Tuesday it will review the tariff schedule on imported steel coils within "
      "48 hours. Importers were asked to hold declarations until the review is published.", "Demo Wire"),
    I("en", 1, "RARE-EARTH-FLASH", "FLASH: Northern mining board suspends export controls exemption for rare-earth shipments",
      "NORTHFIELD, Aldoria", "Licensing exemption paused pending audit",
      "The Northern Mining Board suspended a licensing exemption for rare-earth shipments pending an internal audit, officials "
      "said. Exporters with contracts already in transit will receive guidance by Friday.", "Demo Wire"),
    I("en", 5, "NK-AG-SEMINAR", "Regional studies institute to host seminar on North Korea agricultural statistics",
      "LAKESHORE, Aldoria", "Seminar compares how farm data is compiled",
      "The Lakeshore Institute for Asian Studies will host a one-day seminar on how agricultural statistics are compiled and "
      "compared across countries, with North Korea as one case study. Registration opens next week.", "Sample News Service"),
    I("en", 5, "LAKESHORE-PYONGYANG-EXHIBIT", "Museum exhibit on early Pyongyang architecture opens in Lakeshore",
      "LAKESHORE, Aldoria", "Photo exhibit runs through year end",
      "The Lakeshore City Museum opened a photo exhibit of early Pyongyang architecture on Saturday, drawn from a private "
      "collection lent by a fictional donor. The exhibit runs until December.", "Sample News Service"),
    I("en", 4, "CHIP-EXPORT-CONTROLS", "Semiconductor association asks for clearer export controls guidance on lithography parts",
      "ALDERBRIDGE, Aldoria", "Members unsure how new rules apply to some parts",
      "The fictional Alderbridge Semiconductor Association said members are still unclear how new export controls apply to "
      "certain lithography components. The association plans to send written questions to the trade ministry.", "Demo Wire"),
    I("en", 5, "COFFEE-TARIFF", "Coffee importers warn tariff changes could raise cafe prices",
      "BRIGHTWATER, Aldoria", "Wholesale prices may rise by spring",
      "Coffee importers in Brightwater said a proposed tariff change could add several percent to wholesale prices by spring. "
      "Cafe owners said they are waiting for final rates before adjusting menus.", "Sample News Service"),
    I("en", 6, "STRAIT-SURVEY", "Research vessel schedules seabed survey in fictional channel near Taiwan Strait",
      "MERIDIAN, Aldoria", "Routine mapping, no navigation changes",
      "A fictional research vessel will map the seabed in a channel near the Taiwan Strait next month, the institute said. "
      "The survey is routine and no navigation changes are planned.", "Sample News Service"),
    # Near-duplicate pair A: same story, two fictional agencies, reworded.
    I("en", 4, "SOLAR-TARIFF-DELAY", "Aldoria delays tariff on imported solar panels",
      "NORTHFIELD, Aldoria", "Start date pushed back one quarter",
      "The government of the Republic of Aldoria postponed a planned tariff on imported solar panels by one quarter, the finance "
      "ministry said. Installers said the delay gives them time to clear existing orders.", "Demo Wire"),
    I("en", 4, "SOLAR-TARIFF-DELAY-B", "Aldoria pushes back start of solar panel tariff by three months",
      "NORTHFIELD, Aldoria", "Installers welcome longer lead time",
      "Aldoria's finance ministry has moved back the start date of a new tariff on imported solar panels by three months. "
      "Installers said the postponement gives them time to finish existing projects.", "Sample News Service"),
    # Exact duplicate: byte-identical copy of the item below it (same ID, same time).
    I("en", 6, "LAKESHORE-HARBOR-SHIFTS", "Lakeshore harbor adds night shifts to clear container backlog",
      "LAKESHORE, Aldoria", "Backlog built up after paperwork rule change",
      "Lakeshore harbor will add night shifts this week to clear a container backlog that built up after new export controls "
      "paperwork rules took effect.", "Demo Wire", off=1500),
    I("en", 6, "LAKESHORE-HARBOR-SHIFTS", "Lakeshore harbor adds night shifts to clear container backlog",
      "LAKESHORE, Aldoria", "Backlog built up after paperwork rule change",
      "Lakeshore harbor will add night shifts this week to clear a container backlog that built up after new export controls "
      "paperwork rules took effect.", "Demo Wire", new=False, off=1500),
    # Version 1 and version 2 of one story (same ID, VERSION 2 is the update).
    I("en", 5, "GRID-TENDER", "Ministry of Energy sets date for grid-storage tender",
      "LOWMARK, Aldoria", "Bids to open in the second quarter",
      "The fictional Ministry of Energy said it will open bids for a grid-storage tender in the second quarter. Details will be "
      "published on the ministry website.", "Demo Wire", off=900),
    I("en", 5, "GRID-TENDER", "UPDATE: Ministry of Energy moves grid-storage tender bid date to next month",
      "LOWMARK, Aldoria", "Bid date moved for more public comment",
      "The fictional Ministry of Energy has moved the grid-storage tender bid date to next month to allow more public comment.",
      "Demo Wire", new=False, ver=2, off=150),
    I("en", 3, "TARIFF-EXEMPTION-FAQ", "Harbor authority publishes FAQ on tariff exemptions for export controls compliance",
      "BRIGHTWATER, Aldoria", "Guidance for importers and exporters",
      "The Brightwater harbor authority published a question-and-answer sheet on which tariff exemptions apply to shipments "
      "that must also meet export controls rules.", "Sample News Service"),
    I("en", 6, "LOWMARK-RAIN", "Heavy rain expected across Lowmark valley through Friday",
      "LOWMARK, Aldoria", "Flooding possible on low roads",
      "Forecasters in Lowmark expect steady rain across the valley through Friday, with flooding possible on low-lying roads.",
      "Sample News Service"),
    I("en", 6, "HARBOR-CITY-OPENER", "Harbor City FC wins 3-1 in season opener",
      "HARBOR CITY, Aldoria", "Home crowd of about 9,000",
      "Harbor City FC won 3-1 at home on Sunday in its season opener before a crowd of about 9,000.", "Sample News Service"),
    I("en", 6, "VELLUM-EDITOR", "Startup Vellum releases open-source photo editor",
      "RIVERTON, Aldoria", "Plugin system for third-party filters",
      "The fictional startup Vellum released an open-source photo editor on Monday, with a plugin system for third-party filters.",
      "Demo Wire"),
    I("en", 7, "LANTERN-FESTIVAL", "Lantern Festival draws record crowds to riverside park",
      "RIVERTON, Aldoria", "Night performances and food stalls",
      "Organizers of the Lantern Festival said attendance reached a record this weekend, with food stalls and night performances.",
      "Demo Wire"),
    I("en", 8, "DAILY-HOROSCOPE", "Daily horoscope: what the stars suggest for Thursday",
      "LOWMARK, Aldoria", "Weekly column",
      "Your week ahead brings small surprises and a chance to rest.", "Sample News Service"),
    I("en", 7, "YOUTH-TOURNAMENT-SCORES", "Live scores and highlights from the Northfield tournament",
      "NORTHFIELD, Aldoria", "Youth tournament final round",
      "Scores update throughout the day as the Northfield youth tournament enters its final round.", "Sample News Service"),
    I("en", 6, "EASTMOOR-CLINIC", "Clinic network in Eastmoor expands free vaccination hours",
      "EASTMOOR, Aldoria", "Extra evening sessions added",
      "The Eastmoor clinic network will add evening vaccination sessions at no charge starting next month.", "Demo Wire"),
    I("en", 6, "RIDGEWAY-DESIGN", "Ridgeway university ranks higher in regional design survey",
      "RIDGEWAY, Aldoria", "Survey of 40 schools",
      "Ridgeway university moved up two places in a regional design school survey published this week.", "Sample News Service"),
    I("en", 7, "LOWMARK-SCIENCE-WEEKEND", "Museum opens children's science weekend in Lowmark",
      "LOWMARK, Aldoria", "Hands-on activities for families",
      "The Lowmark science museum opens a weekend of hands-on activities for families this Saturday.", "Demo Wire"),

    # --- Korean -----------------------------------------------------------------------------------------------------
    I("ko", 2, "PORT-TARIFF-FLASH-KO", "속보: 예시항만공사, 관세 조정 긴급 검토 착수",
      "예시시", "수입 철강 관세 긴급 검토",
      "예시항만공사는 24일 수입 철강 제품의 관세 조정안을 긴급 검토한다고 밝혔다. 검토 결과는 48시간 안에 공지될 예정이다.",
      "예시통신"),
    I("ko", 4, "CHIP-EXPORT-CONTROLS-KO", "가상 반도체협회, 수출통제 세부 지침 질의 답변 발표",
      "예시시", "회원사 질문에 답변",
      "예시반도체협회는 신규 수출통제 규정의 세부 적용 기준에 대한 회원사 질의 답변을 발표했다. 협회는 추가 설명회를 다음 달 열 계획이라고 밝혔다.",
      "예시통신"),
    I("ko", 5, "NK-STATS-SEMINAR-KO", "예시대학 동아시아연구소, 북한 경제 통계 세미나 개최",
      "예시시", "통계 수집 방식 비교 세미나",
      "예시대학 동아시아연구소는 다음 달 북한 경제 통계의 수집 방식을 비교하는 세미나를 연다고 밝혔다. 참가 신청은 다음 주부터 받는다.",
      "예시뉴스서비스"),
    I("ko", 5, "IMPORT-FRUIT-TARIFF-KO", "예시농산물시장, 수입 관세 인하 이후 가격 동향 분석",
      "예시시", "도매가격 변화 자료 공개",
      "예시농산물시장은 수입 과일에 대한 관세 인하 이후 도매가격 변화를 분석한 자료를 공개했다. 소비자 가격은 아직 큰 변화가 없었다고 밝혔다.",
      "예시통신"),
    I("ko", 3, "EXPORT-CONTROL-REPORT-KO", "예시경제연구원 보고서: 수출통제가 중소기업 수출에 미치는 영향 제한적",
      "예시시", "중소기업 수출액 영향 분석",
      "예시경제연구원이 발표한 보고서는 수출통제 강화가 중소기업의 전체 수출액에 미치는 영향이 제한적이라고 분석했다. 다만 특정 부품 업종은 주의가 필요하다고 덧붙였다.",
      "예시통신"),
    I("ko", 6, "NK-FOOD-EXHIBIT-KO", "북한 음식 문화 다룬 예시 전시회 개막",
      "예시시", "가상 문화재단 전시",
      "예시문화재단이 북한 음식 문화를 소개하는 가상 전시회를 열었다. 전시는 다음 달까지 이어진다.",
      "예시뉴스서비스"),
    I("ko", 6, "CENTRAL-RAIN-KO", "중부 지방 주말 저녁 소나기, 예시기상청 예보",
      "예시시", "주말 저녁 소나기 예보",
      "예시기상청은 중부 지방에 주말 저녁 한때 소나기가 내릴 수 있다고 예보했다.",
      "예시통신"),
    I("ko", 6, "YEXI-FC-OPENER-KO", "예시FC, 홈 개막전서 2대1 승리",
      "예시시", "홈 개막전 결과",
      "예시FC가 지난 주말 홈 개막전에서 2대1로 이겼다. 후반 교체 선수의 득점이 결승골이 됐다.",
      "예시뉴스서비스"),
    I("ko", 7, "RIVERSIDE-NIGHT-SHOW-KO", "강변 야간 공연 축제, 주말 관객 몰려",
      "예시시", "야간 공연과 먹거리 부스",
      "강변 야간 공연 축제에 주말 관객이 몰렸다고 주최 측이 밝혔다. 먹거리 부스는 밤늦게까지 운영됐다.",
      "예시통신"),
    I("ko", 6, "OPEN-SOURCE-TRANSLATOR-KO", "가상 스타트업, 오픈소스 번역 도구 공개",
      "예시시", "플러그인 구조 지원",
      "가상 스타트업 예시랩은 오픈소스 번역 도구를 공개했다. 제3자 플러그인을 붙일 수 있는 구조다.",
      "예시뉴스서비스"),
    I("ko", 6, "NEIGHBORHOOD-CLINIC-KO", "동네 의원, 야간 진료 시간 확대",
      "예시시", "야간 진료 확대",
      "예시시 동네 의원들이 다음 달부터 야간 진료 시간을 늘린다고 밝혔다.",
      "예시통신"),
    I("ko", 7, "LIBRARY-WINTER-KO", "예시시 도서관, 겨울 독서 프로그램 참가자 모집",
      "예시시", "겨울 독서 프로그램",
      "예시시 도서관은 겨울 독서 프로그램 참가자를 모집한다고 밝혔다. 신청은 이번 주 금요일까지 받는다.",
      "예시뉴스서비스"),
    # Near-duplicate pair B (Korean).
    I("ko", 4, "TARIFF-REFUND-KO", "예시산업부, 관세 환급 기준 개정 예고",
      "예시시", "환급 기준 개정 예고",
      "예시산업부는 수출 기업의 관세 환급 기준을 개정하겠다고 예고했다. 의견 수렴 기간은 2주다.",
      "예시통신"),
    I("ko", 4, "TARIFF-REFUND-KO-B", "관세 환급 요건 개정안 예고, 예시산업부 의견 수렴",
      "예시시", "의견 수렴 2주",
      "예시산업부가 관세 환급 요건을 바꾸는 개정안을 예고했으며, 의견 수렴은 2주간 진행된다.",
      "예시뉴스서비스"),

    # --- Chinese (simplified) ---------------------------------------------------------------------------------------
    I("zh", 2, "PORT-TARIFF-FLASH-ZH", "快讯：示例港口宣布临时调整关税查验流程",
      "示例市", "临时调整钢材关税查验",
      "示例港口管理局周二宣布，将临时调整进口钢材的关税查验流程，相关细则将在两日内公布。",
      "示例通讯社"),
    I("zh", 4, "CHIP-EXPORT-CONTROLS-ZH", "示例半导体协会：出口管制新规细则征求意见",
      "示例市", "光刻零部件适用范围有疑问",
      "示例半导体协会表示，会员对新出口管制规定中部分光刻设备零部件的适用范围仍有疑问，已向主管部门提交书面问题。",
      "示例通讯社"),
    I("zh", 5, "NK-AGRI-SEMINAR-ZH", "示例大学亚洲研究中心举办朝鲜农业数据研讨会",
      "示例市", "比较农业统计收集方法",
      "示例大学亚洲研究中心将于下月举办研讨会，比较不同国家农业统计的收集方法，朝鲜为案例之一。报名下周开始。",
      "示例新闻社"),
    I("zh", 5, "PYONGYANG-EXHIBIT-ZH", "示例博物馆开幕：早期平壤建筑照片展",
      "示例市", "照片展持续至年底",
      "示例博物馆周末开幕，展出一组由虚构收藏者提供的早期平壤建筑照片。展览持续至年底。",
      "示例通讯社"),
    I("zh", 6, "CITY-WEATHER-ZH", "示例市天气：周末多云转晴",
      "示例市", "周末天气",
      "示例市气象台预报，周末多云转晴，气温较上周略有回升。",
      "示例通讯社"),
    I("zh", 6, "TEAM-OPENER-ZH", "示例队以3比1赢得赛季开幕战",
      "示例市", "赛季开幕战",
      "示例队在周日的赛季开幕战中以3比1取胜，主场观众约九千人。",
      "示例新闻社"),
    I("zh", 7, "OPEN-SOURCE-EDITOR-ZH", "示例科技公司发布开源图片编辑工具",
      "示例市", "支持插件扩展",
      "虚构科技公司示例科技发布了一款开源图片编辑工具，支持第三方滤镜插件。",
      "示例通讯社"),
    I("zh", 6, "NIGHT-BUS-ZH", "示例城市推出夜间公交加密班次",
      "示例市", "夜间班次增加",
      "示例城市从下月起在夜间高峰时段加密公交班次，市交通部门表示将根据乘客量调整。",
      "示例新闻社"),
    # Near-duplicate pair C (Chinese).
    I("zh", 4, "TARIFF-ORDERS-ZH", "示例经济研究院：关税变动或影响出口订单",
      "示例市", "两个季度内可能影响订单",
      "示例经济研究院发布的简报认为，拟议中的关税变动可能在两个季度内影响部分出口订单。",
      "示例通讯社"),
    I("zh", 4, "TARIFF-ORDERS-ZH-B", "关税调整可能影响出口订单，示例研究院提示风险",
      "示例市", "简报提示风险",
      "示例研究院在最新简报中提示，拟议的关税调整或会在两个季度内对部分出口订单造成影响。",
      "示例新闻社"),
]

assert len(ITEMS) == 48, len(ITEMS)


def render(item: dict, idx: int, now_utc: datetime, story_id: int) -> tuple[str, str]:
    lang = item["lang"]
    if item["off"] is not None:
        minutes = item["off"]
    else:
        minutes = 30 + ((idx * 37) % 48) * 59  # spreads the 48 files over ~47 hours, interleaved by language
    stamp = (now_utc - timedelta(minutes=minutes)).astimezone(TZ[lang]).isoformat(timespec="seconds")
    footer = FOOTER[lang].format(m=MARK, a=item["agency"])
    header = "\n".join([
        "SYNTHETIC: true",
        f"ID: DEMO-{now_utc:%Y%m%d}-{story_id:04d}",
        f"VERSION: {item['ver']}",
        f"VERSIONCREATED: {stamp}",
        f"LANGUAGE: {lang}",
        f"URGENCY: {item['urg']}",
        f"SLUG: {item['slug']}",
        f"HEADLINE: {item['head']}",
        f"DATELINE: {item['place']}",
        f"DESCRIPTION: {item['desc']}",
        "BODY:",
    ])
    text = f"{header}\n{item['text']}\n\n{footer}\n"
    name = f"demo_{idx + 1:02d}_{lang}_{item['slug'].lower()}"
    if item["ver"] > 1:
        name += f"_v{item['ver']}"
    return name + ".txt", text


def parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, type=Path, help="output directory (created if missing)")
    ap.add_argument("--now", default=None, help="reference time, ISO 8601 (default: current UTC)")
    args = ap.parse_args()

    now_utc = parse_now(args.now)
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    story_id = 0
    for idx, item in enumerate(ITEMS):
        if item["new"]:
            story_id += 1
        name, text = render(item, idx, now_utc, story_id)
        (out / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(ITEMS)} synthetic wire files to {out}")


if __name__ == "__main__":
    main()
