from dataclasses import asdict, dataclass, field
from typing import List, Optional

# === 热榜 ===


@dataclass
class HotsearchItem:
    title: str
    heat_str: str = ""
    heat_num: int = 0
    label_name: str = ""
    rating: Optional[dict] = None


@dataclass
class PlatformResult:
    platform: str
    display_name: str
    items: List[HotsearchItem] = field(default_factory=list)

    def format_text(self) -> str:
        lines = [f"🔥 {self.display_name}热榜 TOP {len(self.items)}", ""]
        for i, item in enumerate(self.items, 1):
            label = f" [{item.label_name}]" if item.label_name else ""
            heat_display = ""
            if item.heat_num >= 10000:
                heat_display = f" {item.heat_num // 10000}万"
            elif item.heat_num:
                heat_display = f" {item.heat_num}"
            lines.append(f"{i}. {item.title}{label}{heat_display}")
            if item.rating and item.rating.get("value"):
                lines.append(
                    f"   评分: {item.rating['value']} ({item.rating.get('count', 0)}人评价)"
                )
            elif self.platform == "douban":
                lines.append("   评分: 暂无")
            if item.heat_str and self.platform != "zhihu":
                lines.append(f"   热度: {item.heat_str}")
            lines.append("")
        return "\n".join(lines)


@dataclass
class HotsearchData:
    platforms: List[PlatformResult] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "HotsearchData":
        return cls(
            platforms=[
                PlatformResult(
                    platform=p.get("platform", ""),
                    display_name=p.get("display_name", ""),
                    items=[HotsearchItem(**i) for i in p.get("items", [])],
                )
                for p in d.get("platforms", [])
            ]
        )

    def to_dict(self) -> dict:
        return {
            "platforms": [
                {
                    "platform": p.platform,
                    "display_name": p.display_name,
                    "items": [asdict(i) for i in p.items],
                }
                for p in self.platforms
            ]
        }

    def format_text(self) -> str:
        return "\n\n".join(p.format_text() for p in self.platforms).strip()


# === AI 新闻 ===


@dataclass
class AINewsItem:
    title: str
    link: str = ""
    date: str = ""
    desc: str = ""


@dataclass
class AINewsSource:
    source: str
    display_name: str
    items: List[AINewsItem] = field(default_factory=list)

    def format_text(self) -> str:
        lines = [f"🤖 {self.display_name} TOP {len(self.items)}", ""]
        for i, item in enumerate(self.items, 1):
            lines.append(f"{i}. {item.title}")
            if item.desc:
                lines.append(f"   {item.desc}")
            lines.append("")
        return "\n".join(lines)


@dataclass
class AINewsData:
    sources: List[AINewsSource] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "AINewsData":
        return cls(
            sources=[
                AINewsSource(
                    source=s.get("source", ""),
                    display_name=s.get("display_name", ""),
                    items=[AINewsItem(**i) for i in s.get("items", [])],
                )
                for s in d.get("sources", [])
            ]
        )

    def to_dict(self) -> dict:
        return {
            "sources": [
                {
                    "source": s.source,
                    "display_name": s.display_name,
                    "items": [asdict(i) for i in s.items],
                }
                for s in self.sources
            ]
        }

    def format_text(self) -> str:
        return "\n\n".join(s.format_text() for s in self.sources).strip()


# === GitHub Trending ===


@dataclass
class GitHubRepo:
    name: str
    stars: int = 0
    desc: str = ""
    lang: str = ""


@dataclass
class GitHubTrendingData:
    items: List[GitHubRepo] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "GitHubTrendingData":
        return cls(items=[GitHubRepo(**i) for i in d.get("items", [])])

    def to_dict(self) -> dict:
        return {"items": [asdict(i) for i in self.items]}

    def format_text(self) -> str:
        lines = [f"🐙 GitHub Trending TOP {len(self.items)}", ""]
        for i, item in enumerate(self.items, 1):
            lang = f" [{item.lang}]" if item.lang else ""
            lines.append(f"{i}. {item.name} ⭐{item.stars}{lang}")
            if item.desc:
                desc = item.desc[:80] + ("..." if len(item.desc) > 80 else "")
                lines.append(f"   {desc}")
            lines.append("")
        return "\n".join(lines)


# === Feeds ===


@dataclass
class VideoItem:
    name: str
    title: str
    link: str = ""


@dataclass
class ReleaseItem:
    name: str
    title: str
    link: str = ""


@dataclass
class LawSummary:
    time: str
    count: int


@dataclass
class FeedsData:
    videos: List[VideoItem] = field(default_factory=list)
    releases: List[ReleaseItem] = field(default_factory=list)
    laws: Optional[LawSummary] = None
    laws_shanghai: Optional[LawSummary] = None

    @classmethod
    def from_daily_dict(cls, d: dict) -> "FeedsData":
        feeds = d.get("feeds", {})
        videos = [
            VideoItem(
                name=v.get("name", ""), title=v.get("title", ""), link=v.get("link", "")
            )
            for v in feeds.get("videos", [])
        ]
        releases = [
            ReleaseItem(
                name=r.get("name", ""), title=r.get("title", ""), link=r.get("link", "")
            )
            for r in feeds.get("releases", [])
        ]
        laws_raw = feeds.get("laws")
        laws = (
            LawSummary(time=laws_raw.get("time", ""), count=laws_raw.get("count", 0))
            if laws_raw
            else None
        )
        laws_sh_raw = feeds.get("laws_shanghai")
        laws_sh = (
            LawSummary(
                time=laws_sh_raw.get("time", ""), count=laws_sh_raw.get("count", 0)
            )
            if laws_sh_raw
            else None
        )
        return cls(videos=videos, releases=releases, laws=laws, laws_shanghai=laws_sh)

    def format_text(self) -> str:
        lines = ["# 24小时数据简报\n"]
        if self.videos:
            lines.append("## 视频更新")
            for v in self.videos:
                lines.append(f"- {v.name}: {v.title}")
            lines.append("")
        else:
            lines.append("## 视频更新")
            lines.append("无更新")
            lines.append("")
        if self.releases:
            lines.append("## 开源发布")
            for r in self.releases:
                lines.append(f"- {r.name}: {r.title}")
            lines.append("")
        else:
            lines.append("## 开源发布")
            lines.append("无更新")
            lines.append("")
        if self.laws:
            lines.append(
                f"## 新法速递\n- 国家法规: {self.laws.count}条 ({self.laws.time})"
            )
            lines.append("")
        if self.laws_shanghai:
            lines.append(
                f"## 上海法规\n- 上海法规: {self.laws_shanghai.count}条 ({self.laws_shanghai.time})"
            )
            lines.append("")
        return "\n".join(lines)
