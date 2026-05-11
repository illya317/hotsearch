from dataclasses import asdict, dataclass, field, fields


def _filter_kwargs(cls, kwargs: dict) -> dict:
    """Keep only kwargs that match the dataclass fields."""
    valid = {f.name for f in fields(cls)}
    return {k: v for k, v in kwargs.items() if k in valid}


# === 热榜 ===


@dataclass
class HotsearchItem:
    title: str
    heat_str: str = ""
    heat_num: int = 0
    label_name: str = ""
    rating: dict | None = None
    item_key: str = ""


@dataclass
class PlatformResult:
    platform: str
    display_name: str
    items: list[HotsearchItem] = field(default_factory=list)

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
    platforms: list[PlatformResult] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "HotsearchData":
        return cls(
            platforms=[
                PlatformResult(
                    platform=p.get("platform", ""),
                    display_name=p.get("display_name", ""),
                    items=[HotsearchItem(**_filter_kwargs(HotsearchItem, i)) for i in p.get("items", [])],
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
    items: list[AINewsItem] = field(default_factory=list)

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
    sources: list[AINewsSource] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "AINewsData":
        return cls(
            sources=[
                AINewsSource(
                    source=s.get("source", ""),
                    display_name=s.get("display_name", ""),
                    items=[AINewsItem(**_filter_kwargs(AINewsItem, i)) for i in s.get("items", [])],
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
    items: list[GitHubRepo] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "GitHubTrendingData":
        return cls(items=[GitHubRepo(**_filter_kwargs(GitHubRepo, i)) for i in d.get("items", [])])

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


