#!/usr/bin/env python3
"""Build the deterministic OpenNutri voice/text beta benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import struct
import subprocess
import wave
from pathlib import Path
from typing import Any


VERSION = "0.1.0"
CORE_VERSION = "0.3.0"
SAMPLE_RATE = 16_000

BANANA = "c23af8bb-739c-5ae1-ac9c-6182cf632555"
APPLE = "e17d8b70-a69f-5d05-adcb-0cf184609134"
EGG = "15e3e7bd-31e8-5f97-a21d-e53ab61c55bd"
RICE_COOKED = "b04c3294-aea8-502a-8951-30a04d1a1936"
RICE_RAW = "945026d6-6464-52fc-8cf8-4a4f72654331"
MILK = "e1e57b62-5be5-51f7-a0bb-dc0e249179ee"
CHICKEN_GRILLED = "7e7ceb2f-1570-54eb-b195-c56bff952f9f"
YOGURT = "60d9870d-3992-5288-9d9e-5cce340850d3"
ALMONDS = "4bedbd8b-6da2-5a7a-afca-568131dea2f8"
POTATO = "6844fe80-26f7-53e0-b978-2b09cb0f78b2"
TUNA = "203575a6-cfbc-57c0-bfbf-b9dff6bcee0a"
SALMON = "5f87ab90-2f33-5a9c-a446-010d3447539a"
COFFEE = "b5ba7d57-c01f-5a4c-96d9-5000f2f285bc"
ORANGE = "c63afe19-f357-51fe-b313-ab2bb1cfa5cb"
BREAD = "df5f752f-572c-53a9-8e38-9660aa3861db"
TOAST = "5f5d73a6-c10d-5e5f-b4ae-12a1318fcd9f"
CHICKEN_LEG_RAW = "b83a4e19-5d6a-57dd-87ea-ea4a02d0e438"


def concept(
    *food_ids: str,
    quantity: str,
    clarifications: tuple[str, ...] = (),
    no_match: bool = False,
) -> dict[str, Any]:
    return {
        "acceptable_food_ids": list(food_ids),
        "quantity": quantity,
        "required_clarifications": list(clarifications),
        "no_match": no_match,
    }


SEEDS: tuple[dict[str, Any], ...] = (
    {
        "en": "100 grams of raw banana",
        "tr": "100 gram çiğ muz",
        "tags": ("grams", "raw"),
        "concepts": (concept(BANANA, quantity="resolved"),),
    },
    {
        "en": "one medium banana",
        "tr": "bir orta boy muz",
        "tags": ("source_portion", "colloquial"),
        "concepts": (concept(BANANA, quantity="resolved"),),
    },
    {
        "en": "150 grams of raw apple",
        "tr": "150 gram çiğ elma",
        "tags": ("grams", "raw"),
        "concepts": (concept(APPLE, quantity="resolved"),),
    },
    {
        "en": "two hard-boiled whole eggs",
        "tr": "iki katı pişmiş bütün yumurta",
        "tags": ("source_portion", "cooking_state"),
        "concepts": (concept(EGG, quantity="resolved"),),
    },
    {
        "en": "200 grams of cooked white rice with no added fat",
        "tr": "yağ eklenmemiş 200 gram pişmiş beyaz pirinç",
        "tags": ("grams", "cooking_state"),
        "concepts": (concept(RICE_COOKED, quantity="resolved"),),
    },
    {
        "en": "250 milliliters of whole milk",
        "tr": "250 mililitre tam yağlı süt",
        "tags": ("unsupported_conversion", "missing_quantity"),
        "concepts": (concept(MILK, quantity="unresolved", clarifications=("quantity",)),),
    },
    {
        "en": "120 grams of grilled chicken breast without sauce, skin not eaten",
        "tr": "sossuz ızgara tavuk göğsü, derisi yenmemiş, 120 gram",
        "tags": ("grams", "skin", "cooking_state"),
        "concepts": (concept(CHICKEN_GRILLED, quantity="resolved"),),
    },
    {
        "en": "one cup of plain whole-milk yogurt",
        "tr": "bir su bardağı sade tam yağlı yoğurt",
        "tags": ("source_portion",),
        "concepts": (concept(YOGURT, quantity="resolved"),),
    },
    {
        "en": "30 grams of unsalted almonds",
        "tr": "30 gram tuzsuz badem",
        "tags": ("grams", "colloquial"),
        "concepts": (concept(ALMONDS, quantity="resolved"),),
    },
    {
        "en": "350 grams of baked potato, flesh and skin, without salt",
        "tr": "eti ve kabuğuyla tuzsuz fırın patates, 350 gram",
        "tags": ("skin", "grams", "cooking_state"),
        "concepts": (concept(POTATO, quantity="resolved"),),
    },
    {
        "en": "100 grams of canned light tuna in water, drained",
        "tr": "suda konserve, süzülmüş 100 gram light ton balığı",
        "tags": ("drained", "grams"),
        "concepts": (concept(TUNA, quantity="resolved"),),
    },
    {
        "en": "180 grams of raw salmon",
        "tr": "180 gram çiğ somon",
        "tags": ("raw", "grams"),
        "concepts": (concept(SALMON, quantity="resolved"),),
    },
    {
        "en": "one cup of brewed coffee",
        "tr": "bir fincan demlenmiş kahve",
        "tags": ("source_portion",),
        "concepts": (concept(COFFEE, quantity="resolved"),),
    },
    {
        "en": "one medium raw orange",
        "tr": "bir orta boy çiğ portakal",
        "tags": ("source_portion", "raw"),
        "concepts": (concept(ORANGE, quantity="resolved"),),
    },
    {
        "en": "two slices of bread, type not specified",
        "tr": "türü belirtilmemiş iki dilim ekmek",
        "tags": ("unspecified", "source_portion"),
        "concepts": (
            concept(
                BREAD,
                quantity="resolved",
                clarifications=("unspecified_food",),
            ),
        ),
    },
    {
        "en": "100 grams of raw banana and 200 grams of whole milk",
        "tr": "100 gram çiğ muz ve 200 gram tam yağlı süt",
        "tags": ("multiple_foods", "grams"),
        "concepts": (
            concept(BANANA, quantity="resolved"),
            concept(MILK, quantity="resolved"),
        ),
    },
    {
        "en": "a hard-boiled egg and toasted bread",
        "tr": "katı pişmiş yumurta ve kızarmış ekmek",
        "tags": ("multiple_foods", "missing_quantity", "cooking_state"),
        "concepts": (
            concept(EGG, quantity="unresolved", clarifications=("quantity",)),
            concept(TOAST, quantity="unresolved", clarifications=("quantity",)),
        ),
    },
    {
        "en": "plain whole-milk yogurt",
        "tr": "sade tam yağlı yoğurt",
        "tags": ("missing_quantity",),
        "concepts": (concept(YOGURT, quantity="unresolved", clarifications=("quantity",)),),
    },
    {
        "en": "300 grams as purchased of raw chicken leg with bone and skin",
        "tr": "kemikli ve derili çiğ tavuk budu, satın alındığı haliyle 300 gram",
        "tags": ("as_purchased", "bone", "skin", "raw"),
        "concepts": (concept(CHICKEN_LEG_RAW, quantity="resolved"),),
    },
    {
        "en": "100 grams of raw bannana",
        "tr": "100 gram çiy muz",
        "tags": ("transcription_error", "grams"),
        "concepts": (concept(BANANA, quantity="resolved"),),
    },
    {
        "en": "a cuppa joe",
        "tr": "bir sade kahve",
        "tags": ("colloquial", "missing_quantity"),
        "concepts": (concept(COFFEE, quantity="unresolved", clarifications=("quantity",)),),
    },
    {
        "en": "one bowl of my homemade mantı with secret sauce",
        "tr": "özel soslu ev yapımı bir kase mantı",
        "tags": ("no_match_dish", "recipe"),
        "concepts": (concept(quantity="unresolved", clarifications=("food",), no_match=True),),
    },
    {
        "en": "grandma's leftover chicken surprise casserole",
        "tr": "anneannemin kalan tavuklu sürpriz güveci",
        "tags": ("no_match_dish", "recipe", "missing_quantity"),
        "concepts": (concept(quantity="unresolved", clarifications=("food",), no_match=True),),
    },
    {
        "en": "200 grams of white rice",
        "tr": "200 gram beyaz pirinç",
        "tags": ("raw_cooked_ambiguity", "grams"),
        "concepts": (
            concept(
                RICE_COOKED,
                RICE_RAW,
                quantity="resolved",
                clarifications=("preparation",),
            ),
        ),
    },
)

VARIANTS = {
    "en": (
        "{phrase}",
        "Please log {phrase}.",
        "For this meal I had {phrase}.",
        "Add {phrase} to my diary.",
        "{phrase}, that's everything.",
    ),
    "tr": (
        "{phrase}",
        "Lütfen {phrase} kaydet.",
        "Bu öğünde {phrase} tükettim.",
        "Günlüğüme {phrase} ekle.",
        "{phrase}, hepsi bu.",
    ),
}


def _validate_food_ids(database: Path) -> None:
    expected = {
        food_id
        for seed in SEEDS
        for item in seed["concepts"]
        for food_id in item["acceptable_food_ids"]
    }
    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            f"SELECT food_id FROM foods WHERE food_id IN ({','.join('?' for _ in expected)})",
            sorted(expected),
        ).fetchall()
        found = {row[0] for row in rows}
    finally:
        connection.close()
    missing = sorted(expected - found)
    if missing:
        raise SystemExit(f"Core {CORE_VERSION} is missing benchmark IDs: {missing}")


def _resample_pcm16(samples: bytes, source_rate: int) -> bytes:
    values = struct.unpack(f"<{len(samples) // 2}h", samples)
    output_length = round(len(values) * SAMPLE_RATE / source_rate)
    output: list[int] = []
    for index in range(output_length):
        position = index * source_rate / SAMPLE_RATE
        lower = min(int(position), len(values) - 1)
        upper = min(lower + 1, len(values) - 1)
        fraction = position - lower
        output.append(round(values[lower] * (1 - fraction) + values[upper] * fraction))
    return struct.pack(f"<{len(output)}h", *output)


def _render_audio(
    *,
    text: str,
    language: str,
    destination: Path,
    espeak: Path,
    espeak_data: Path | None,
    library_path: Path | None,
) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = destination.with_suffix(".source.wav")
    environment = os.environ.copy()
    if espeak_data is not None:
        environment["ESPEAK_DATA_PATH"] = str(espeak_data)
    if library_path is not None:
        environment["LD_LIBRARY_PATH"] = str(library_path)
    subprocess.run(
        [
            str(espeak),
            "-v",
            "en-us" if language == "en" else "tr",
            "-s",
            "155",
            "-w",
            str(source),
            text,
        ],
        check=True,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with wave.open(str(source), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise SystemExit(f"Unexpected eSpeak format for {source}")
        frames = wav.readframes(wav.getnframes())
        converted = _resample_pcm16(frames, wav.getframerate())
    source.unlink()
    with wave.open(str(destination), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(converted)
    if destination.stat().st_size > 1024 * 1024:
        raise SystemExit(f"Audio fixture exceeds 1 MB: {destination}")
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("cases.jsonl"))
    parser.add_argument("--render-audio", action="store_true")
    parser.add_argument("--espeak", type=Path)
    parser.add_argument("--espeak-data", type=Path)
    parser.add_argument("--library-path", type=Path)
    args = parser.parse_args()

    _validate_food_ids(args.core_db)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = []
    expected_audio_paths: set[Path] = set()
    for language in ("en", "tr"):
        sequence = 0
        for seed_index, seed in enumerate(SEEDS, start=1):
            for variant_index, template in enumerate(VARIANTS[language], start=1):
                sequence += 1
                utterance = template.format(phrase=seed[language])
                modality = "audio" if variant_index == 1 else "text"
                case_id = f"voice-v{VERSION}-{language}-{sequence:03d}"
                case: dict[str, Any] = {
                    "id": case_id,
                    "benchmark_version": VERSION,
                    "core_version": CORE_VERSION,
                    "language": language,
                    "modality": modality,
                    "utterance": utterance,
                    "tags": sorted(seed["tags"]),
                    "seed": seed_index,
                    "expected": {
                        "concept_count": len(seed["concepts"]),
                        "concepts": list(seed["concepts"]),
                    },
                }
                if modality == "audio":
                    relative_audio = Path("audio") / language / f"{case_id}.wav"
                    case["audio_path"] = relative_audio.as_posix()
                    destination = output.parent / relative_audio
                    expected_audio_paths.add(destination.resolve())
                    if args.render_audio:
                        if args.espeak is None:
                            raise SystemExit("--espeak is required with --render-audio")
                        case["audio_sha256"] = _render_audio(
                            text=utterance,
                            language=language,
                            destination=destination,
                            espeak=args.espeak,
                            espeak_data=args.espeak_data,
                            library_path=args.library_path,
                        )
                    elif destination.is_file():
                        case["audio_sha256"] = hashlib.sha256(
                            destination.read_bytes()
                        ).hexdigest()
                cases.append(case)

    if args.render_audio:
        audio_root = output.parent / "audio"
        for existing_audio in audio_root.rglob("*.wav"):
            if existing_audio.resolve() not in expected_audio_paths:
                existing_audio.unlink()

    output.write_text(
        "".join(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n" for case in cases),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(cases)} cases "
        f"({sum(case['modality'] == 'audio' for case in cases)} audio) to {output}"
    )


if __name__ == "__main__":
    main()
