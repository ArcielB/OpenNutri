from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"
FUNNEL_SOURCE = (
    BASE_DIR.parent.parent
    / "services"
    / "data-pipeline"
    / "data"
    / "crawl_tr_live_2026-03-30b"
    / "raw_pdfs"
    / "_harvest_metadata.json"
)

plt.rcParams["font.family"] = "DejaVu Sans"


def setup_canvas(figsize: tuple[float, float]):
    fig, ax = plt.subplots(figsize=figsize, dpi=180)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def add_box(ax, x, y, w, h, title, body, *, fc, ec="#284b63", title_color="#0f172a"):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.02",
        linewidth=1.5,
        facecolor=fc,
        edgecolor=ec,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h * 0.72, title, ha="center", va="center", fontsize=10, weight="bold", color=title_color)
    ax.text(x + w / 2, y + h * 0.35, body, ha="center", va="center", fontsize=8.5, color="#1f2937", wrap=True)


def add_arrow(ax, start, end, *, text=None):
    arrow = FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=14, linewidth=1.5, color="#475569")
    ax.add_patch(arrow)
    if text:
        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2
        ax.text(mid_x, mid_y + 0.03, text, ha="center", va="center", fontsize=8, color="#334155")


def save(fig, name: str):
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    target = ASSET_DIR / name
    fig.savefig(target, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def generate_architecture():
    fig, ax = setup_canvas((12, 7))
    ax.text(0.5, 0.95, "OpenNutri Arasınav Mimarisi", ha="center", va="center", fontsize=18, weight="bold", color="#0f172a")

    add_box(
        ax, 0.05, 0.62, 0.22, 0.18,
        "Bilimsel Kaynaklar",
        "Europe PMC\nOpenAlex\nSemantic Scholar\nDergiPark",
        fc="#dbeafe",
    )
    add_box(
        ax, 0.39, 0.62, 0.22, 0.18,
        "Crawler ve Filtreleme",
        "Search gate\nMetadata filter\nPDF edinme\nPDF doğrulama",
        fc="#dcfce7",
    )
    add_box(
        ax, 0.73, 0.62, 0.22, 0.18,
        "Supabase Katmanı",
        "papers\nsearch hits/batches\nstorage\nRLS politikaları",
        fc="#fde68a",
    )
    add_box(
        ax, 0.12, 0.23, 0.26, 0.2,
        "Annotator Arayüzü",
        "PDF görüntüleme\nhighlight + quick add\ndinamik food/nutrient formu\ntest mode",
        fc="#fce7f3",
    )
    add_box(
        ax, 0.62, 0.23, 0.26, 0.2,
        "Feedback ve Refill",
        "paper_label_events\npaper_global_labels\nupdate_terms.py\nensure_paper_stock.py",
        fc="#e9d5ff",
    )

    add_arrow(ax, (0.27, 0.71), (0.39, 0.71), text="metadata")
    add_arrow(ax, (0.61, 0.71), (0.73, 0.71), text="kabul edilen makale + kanıt")
    add_arrow(ax, (0.84, 0.62), (0.30, 0.43), text="PDF ve makale kuyruğu")
    add_arrow(ax, (0.38, 0.33), (0.62, 0.33), text="etiket olayları")
    add_arrow(ax, (0.75, 0.43), (0.75, 0.62), text="öğrenilmiş terimler / yeni tarama")

    ax.text(
        0.5,
        0.08,
        "Kapalı döngü mantığı: uzman etiketleri yalnızca son çıktı değildir; daha sonraki tarama ve sıralama kararlarını da besler.",
        ha="center",
        va="center",
        fontsize=9,
        color="#334155",
    )
    save(fig, "figure_1_system_architecture.png")


def generate_feedback_data_model():
    fig, ax = setup_canvas((12, 7.5))
    ax.text(0.5, 0.95, "Anotasyon ve Feedback Veri İlişkisi", ha="center", va="center", fontsize=18, weight="bold", color="#0f172a")

    add_box(ax, 0.07, 0.68, 0.18, 0.14, "papers", "Makale kimliği\nkaynak\nworkflow_language\nscore alanları", fc="#dbeafe")
    add_box(ax, 0.30, 0.68, 0.18, 0.14, "annotations", "Kullanıcı başına\npaper durumu\nhas_data", fc="#dcfce7")
    add_box(ax, 0.53, 0.68, 0.18, 0.14, "food_items", "Makaledeki gıda\nsatırları", fc="#dcfce7")
    add_box(ax, 0.76, 0.68, 0.18, 0.14, "annotation_nutrient_values", "Her food item için\ndinamik nutrient satırları", fc="#dcfce7")

    add_box(ax, 0.18, 0.38, 0.24, 0.15, "paper_label_events", "draft / done / skipped\nhas_data\nfood_item_count\nnutrient_value_count", fc="#fde68a")
    add_box(ax, 0.50, 0.38, 0.20, 0.15, "paper_global_labels", "definitely_no_data\nkısa süreli undo", fc="#fde68a")
    add_box(ax, 0.75, 0.37, 0.18, 0.17, "paper_search_hits +\npaper_search_batches", "Sorgu kanıtı\nbatch verimi\nkaynak bazlı izleme", fc="#fce7f3")

    add_box(ax, 0.18, 0.10, 0.26, 0.16, "feedback/update_terms.py", "Olaylardan iyi / kötü /\nçatışmalı örnekleri türetir\nn-gram ve batch skoru üretir", fc="#e9d5ff")
    add_box(ax, 0.56, 0.10, 0.26, 0.16, "crawler_v2.py", "feedback skorlarını\nsoft evidence olarak kullanır\nsonraki adayları seçer", fc="#e9d5ff")

    add_arrow(ax, (0.25, 0.75), (0.30, 0.75))
    add_arrow(ax, (0.48, 0.75), (0.53, 0.75))
    add_arrow(ax, (0.71, 0.75), (0.76, 0.75))
    add_arrow(ax, (0.30, 0.68), (0.30, 0.53))
    add_arrow(ax, (0.58, 0.68), (0.60, 0.53))
    add_arrow(ax, (0.84, 0.68), (0.84, 0.54))
    add_arrow(ax, (0.30, 0.38), (0.31, 0.26))
    add_arrow(ax, (0.60, 0.38), (0.37, 0.26))
    add_arrow(ax, (0.84, 0.37), (0.69, 0.26))
    add_arrow(ax, (0.44, 0.18), (0.56, 0.18), text="öğrenilmiş terimler,\nkaynak öncelikleri,\nbatch skorları")

    save(fig, "figure_2_feedback_data_model.png")


def generate_crawler_funnel():
    fig, ax = plt.subplots(figsize=(11, 6), dpi=180)
    ax.set_facecolor("white")

    labels = [
        "TR ham adaylar",
        "Search gate geçenler",
        "Metadata filter geçenler",
        "PDF fetch başarısız",
        "PDF validation başarısız",
        "Kabul edilenler",
    ]
    values = [142, 137, 78, 32, 31, 3]
    subtitle = "Örnek canlı koşu bulunamadı; varsayılan şema kullanıldı."

    if FUNNEL_SOURCE.exists():
        payload = json.loads(FUNNEL_SOURCE.read_text(encoding="utf-8"))
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        tr_row = summary.get("languages", {}).get("tr", {})
        if isinstance(tr_row, dict):
            labels = [
                "TR hits",
                "Search gate geçenler",
                "Metadata filter geçenler",
                "PDF fetch başarısız",
                "PDF validation başarısız",
                "Kabul edilenler",
            ]
            values = [
                int(tr_row.get("hits", 0)),
                int(tr_row.get("search_gate_pass", 0)),
                int(tr_row.get("metadata_pass", 0)),
                int(tr_row.get("pdf_fetch_fail", 0)),
                int(tr_row.get("pdf_validation_fail", 0)),
                int(tr_row.get("accepted", 0)),
            ]
            subtitle = "Kaynak: services/data-pipeline/data/crawl_tr_live_2026-03-30b/raw_pdfs/_harvest_metadata.json"

    colors = ["#60a5fa", "#38bdf8", "#34d399", "#f59e0b", "#fb7185", "#22c55e"]
    y_positions = list(range(len(labels)))
    ax.barh(y_positions, values, color=colors, edgecolor="#1f2937")
    ax.set_yticks(y_positions, labels)
    ax.invert_yaxis()
    ax.set_xlabel("Kayıt / aşama sayısı")
    ax.set_title("Örnek Crawler Aşama Özeti (30.03.2026 tarihli TR canlı koşu)")

    for idx, value in enumerate(values):
        ax.text(value + max(values) * 0.015, idx, str(value), va="center", fontsize=9, color="#0f172a")

    fig.text(0.02, 0.02, subtitle, fontsize=8.5, color="#475569")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, "figure_3_crawler_funnel_example.png")


def generate_placeholder():
    fig, ax = setup_canvas((11, 6))
    add_box(
        ax,
        0.08,
        0.18,
        0.84,
        0.62,
        "Bu görsel gerçek annotator ekran görüntüsü ile değiştirilmelidir",
        "\n".join(
            [
                "1. apps/expert-annotator içinde npm install && npm run dev çalıştırın.",
                "2. Sisteme giriş yapın ve Annotate sayfasını açın.",
                "3. Aynı karede şunlar görünsün:",
                "   PDF viewer, vurgulanmış bir nutrient, sağdaki food item formu,",
                "   üstte ilerleme / durum alanı.",
                "4. Görseli docs/defense/assets/annotator_screenshot.png olarak kaydedin",
                "   ve rapordaki bu yer tutucu ile değiştirin.",
            ]
        ),
        fc="#f8fafc",
        ec="#64748b",
    )
    ax.text(0.5, 0.86, "Şekil 4 için Yer Tutucu", ha="center", va="center", fontsize=18, weight="bold", color="#0f172a")
    save(fig, "figure_4_annotator_placeholder.png")


def main():
    generate_architecture()
    generate_feedback_data_model()
    generate_crawler_funnel()
    generate_placeholder()
    print("Created assets in", ASSET_DIR)


if __name__ == "__main__":
    main()
