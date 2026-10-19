#!/usr/bin/env python3
"""Look up Huawei mainHelp catalog records and product Profiles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


DEFAULT_CATALOG_URL = (
    "https://smarthome-drcn.dbankcdn.com/device/guide/"
    "ver_202609_hmos/mainHelp.json"
)
DEFAULT_PROFILE_BASE = "https://smarthome-drcn.dbankcdn.com/device/guide"


def read_json(source: str) -> object:
    path = Path(source)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    request = Request(source, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def catalog_record(catalog: object, product_id: str) -> dict[str, object] | None:
    if not isinstance(catalog, list):
        return None
    for item in catalog:
        if isinstance(item, dict) and item.get("DeviceId") == product_id:
            return item
    return None


def profile_summary(profile: object) -> dict[str, object]:
    if not isinstance(profile, dict):
        return {"profile": profile}
    services = []
    for service in profile.get("services", []):
        if not isinstance(service, dict):
            continue
        services.append(
            {
                "serviceId": service.get("serviceId"),
                "serviceType": service.get("serviceType"),
                "characteristics": [
                    {
                        key: characteristic.get(key)
                        for key in (
                            "characteristicName",
                            "characteristicType",
                            "method",
                            "min",
                            "max",
                            "step",
                            "unit",
                            "enumList",
                        )
                        if key in characteristic
                    }
                    for characteristic in service.get("characteristics", [])
                    if isinstance(characteristic, dict)
                ],
            }
        )
    return {
        key: profile.get(key)
        for key in (
            "prodId",
            "deviceModel",
            "deviceTypeId",
            "manufacturerId",
            "protocolType",
            "uiType",
        )
    } | {"services": services}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("product_id", nargs="?")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG_URL)
    parser.add_argument("--profile")
    parser.add_argument("--catalog-only", action="store_true")
    args = parser.parse_args()

    catalog = read_json(args.catalog)
    if not args.product_id:
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
        return 0

    record = catalog_record(catalog, args.product_id)
    output: dict[str, object] = {"catalog": record}
    if not args.catalog_only:
        profile_url = args.profile or (
            f"{DEFAULT_PROFILE_BASE}/{args.product_id}/{args.product_id}.json"
        )
        output["profile_url"] = profile_url
        output["profile"] = profile_summary(read_json(profile_url))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
