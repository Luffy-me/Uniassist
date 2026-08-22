"""Shared fixtures for SUSU connector tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from uniassist.scrapeai.sources.susu.official_regulations import load_yaml_config

SAMPLE_SUSU_HTML = """
<html>
  <body>
    <a href="https://www.susu.ru/sites/default/files/rules/students.pdf">
      Правила внутреннего распорядка обучающихся
    </a>
    <a href="https://www.susu.ru/sites/default/files/rules/charter.pdf">
      Устав университета
    </a>
    <a href="https://www.susu.ru/sites/default/files/rules/transfer.pdf">
      Положение о переводе обучающихся
    </a>
    <a href="https://www.susu.ru/sites/default/files/rules/misc.pdf">
      Документ без явной тематики
    </a>
    <a href="https://k.susu.ru/_olan/_docs/pol_tek_kontr_bsm.pdf">
      Положение о текущем контроле успеваемости
    </a>
    <a href="https://www.susu.ru/ru/university/official/documents">
      Другие локальные нормативные акты
    </a>
  </body>
</html>
"""


@pytest.fixture
def config_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "configs"
        / "susu"
        / "official_regulations.yaml"
    )


@pytest.fixture
def susu_config(config_path: Path) -> dict:
    return load_yaml_config(config_path)
