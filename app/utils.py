from pathlib import Path
from typing import Self

from pydantic import BaseModel

import yaml


class LiteralDumper(yaml.SafeDumper):
    pass


def str_representer(
    dumper: LiteralDumper,
    value: str,
) -> yaml.nodes.ScalarNode:
    style = "|" if "\n" in value else None

    return dumper.represent_scalar(
        "tag:yaml.org,2002:str",
        value,
        style=style,
    )


LiteralDumper.add_representer(str, str_representer)


class YamlBaseModel(BaseModel):
    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls.model_validate(raw)

    def dump_yaml(self) -> str:
        return yaml.dump(
            self.model_dump(mode="json"),
            Dumper=LiteralDumper,
            allow_unicode=True,
            sort_keys=False,
        )
