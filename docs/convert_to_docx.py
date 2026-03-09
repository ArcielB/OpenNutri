import pypandoc

# Sections in order
sections = [
    "sections/section_1_national_gain.md",
    "sections/section_2_objectives.md",
    "sections/section_3_patents_innovation.md",
    "sections/section_4a_method_architecture.md",
    "sections/section_4b_method_data_stats.md",
    "sections/section_5_project_management.md",
    "sections/section_6_widespread_impact.md",
    "sections/ek1_references.md",
]

# Read and concatenate all sections
combined = ""
for path in sections:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    combined += content + "\n\n\\newpage\n\n"

# Write combined markdown
with open("combined_application.md", "w", encoding="utf-8") as f:
    f.write(combined)

# Convert to DOCX
output = pypandoc.convert_file(
    "combined_application.md",
    "docx",
    outputfile="OpenNutri_1005_Application.docx",
    extra_args=[
        "--from=gfm+alerts",
        "--standalone",
    ]
)

print("DOCX created: OpenNutri_1005_Application.docx")
