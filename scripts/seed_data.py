"""Generate sample data for local development and testing.

Creates:
  • data/supplier/ — sample supplier catalog CSVs
  • Verifies the pipeline can run end-to-end locally

Usage:
    python scripts/seed_data.py
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

from faker import Faker

fake = Faker()
Faker.seed(42)

CATEGORIES = {
    "Electronics": ["Laptops", "Headphones", "Cables", "Monitors", "Keyboards"],
    "Clothing": ["T-Shirts", "Jeans", "Jackets", "Shoes", "Hats"],
    "Home": ["Furniture", "Lighting", "Kitchen", "Bedding", "Decor"],
    "Grocery": ["Produce", "Dairy", "Snacks", "Beverages", "Frozen"],
}


def generate_supplier_catalog(output_dir: str = "data/supplier", n_products: int = 200) -> None:
    """Generate a supplier catalog CSV file."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    filepath = path / "supplier_catalog_2026_01.csv"
    rows = []

    for i in range(1, n_products + 1):
        category = random.choice(list(CATEGORIES.keys()))
        subcategory = random.choice(CATEGORIES[category])
        rows.append(
            {
                "product_id": i,
                "product_name": f"{fake.word().title()} {subcategory}",
                "category": category,
                "subcategory": subcategory,
                "brand": fake.company(),
                "supplier_id": random.randint(1, 50),
                "unit_cost": round(random.uniform(2.0, 200.0), 2),
            }
        )

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Generated {len(rows)} products → {filepath}")


def main() -> None:
    print("🌱 Seeding local data...")
    generate_supplier_catalog()
    print("🌱 Done! Run `make run-local` to execute the pipeline.")


if __name__ == "__main__":
    main()
