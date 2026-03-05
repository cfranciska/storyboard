import streamlit as st
import pandas as pd
from openpyxl import Workbook
from io import BytesIO
from openai import OpenAI
import json
import streamlit.components.v1 as components
import base64


# ======================================
# CONFIG
# ======================================

st.set_page_config(page_title="AI Storyboard Builder", layout="wide")

st.markdown("""
<style>
[data-testid="stFileUploaderDropzoneInstructions"] div:nth-child(2) {
    display: none;
}
</style>
""", unsafe_allow_html=True)

API_KEY = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=API_KEY)

MODEL_NAME = "gpt-5-mini"

# ======================================
# SYSTEM PROMPTS
# ======================================

STANDARDIZATION_SYSTEM_PROMPT = """
You are a standardization engine that converts raw inputs into a strictly structured Creative Spec used as a single source of truth for downstream automation.

Rules:
- Return valid JSON only.
- Do not add explanations or commentary.
- Do not invent facts or claims.
- If information is missing or unclear, use "unknown".
- Normalize values when applicable.
- Rank product value propositions by importance based only on the input.
- Extract and restate information concisely.
- Do not validate, evaluate, or optimize.
- Do not include fields outside the defined schema.

Return JSON in the exact structure below:

{
  "product_brand_context": {
    "product_name": "",
    "product_category": "",
    "product_value_propositions_ranked": [
      {
        "rank": 1,
        "value": ""
      }
    ],
    "product_usage": "",
    "mandatory_brand_rules": ""
  },
  "audience_market_context": {
    "target_market": "",
    "region": "",
    "language": "",
    "age_persona": "",
    "key_objections": "",
    "primary_hook_angle": ""
  },
  "campaign_distribution_context": {
    "objective": "",
    "platform": "",
    "story_concept": "",
    "tone": "",
    "cta_intent": ""
  }
}

Notes:
- "product_value_propositions_ranked" must be an array.
- Include all ranks present in the input (rank 1 = highest importance).
- If no value propositions exist, return an empty array.
- If a field is missing, use "unknown".
"""

STORYLINE_SYSTEM_PROMPT = """
You are a Creative Strategist for Brand-Led AI Video Advertising.

You MUST return valid JSON only.
No markdown.
No explanation.
No commentary.

STRICT JSON STRUCTURE:

{
  "variations": [
    {
      "story_variation": "Story Variation 1",
      "concept": "",
      "setting": "",
      "tone": "",
      "shots": [
        {
          "shot": "",
          "scene": "",
          "visual": "",
          "camera": "",
          "vo": "",
          "on_screen_text": "",
          "mood_lighting": "",
          "setting": "",
          "outfit": "",
          "duration": ""
        }
      ]
    }
  ]
}

Rules:
- Match number of variations requested.
- Match number of shots requested.
- Every shot must contain ALL fields.
- Follow user constraints exactly.
- Do not invent product claims.
"""

IMAGE_VIDEO_SYSTEM_PROMPT = """
You are a Brand Advertising Prompt Engineer for AI Image and Video Generation.

Your task is to convert a structured advertising storyboard into:

1) One still image prompt per shot
2) One video generation prompt per shot

Important Context:
- Character image will be provided separately during generation.
- Do NOT re-describe the character’s physical traits.
- Focus only on scene composition, camera framing, environment, lighting, mood, and product staging.

Core Rules:

Image Prompt Rules:
- One still frame only
- No time progression
- No cinematic montage language
- No split frames or collages
- Clear camera framing
- Clear product placement
- Physically shootable setup
- Realistic lighting
- Brand-safe

Video Prompt Rules:
- Describe motion, transitions, and continuity clearly
- Keep production realistic and shootable
- No fantasy, no surrealism
- Maintain environment consistency across shots
- Explicitly describe how product is shown or used
- Avoid vague cinematic wording

VO Rules:
- The storyline is the single source of truth for VO.
- Extract the exact voiceover text directly from the provided storyline.
- Do NOT rewrite.
- Do NOT paraphrase.
- Do NOT modify wording.
- Do NOT improve grammar.
- Preserve punctuation exactly as written.
- Map the correct existing line to each shot.
- If no exact matching sentence exists for a shot, return: VO: none
- One VO line per shot.

Output Structure:

Shot 1
Image Prompt:
Video Prompt:
VO: 

Shot 2
Image Prompt:
Video Prompt:
VO: 

Continue until all shots are completed.

Do not add commentary.
Do not add explanation.
Only output structured prompts.
"""

CHARACTER_SYSTEM_PROMPT = """
<You are a Brand Advertising Character Persona Generator.

Your task is to generate realistic, commercially viable human character personas optimized for brand advertisements and AI image generation.

Core Responsibilities
- Character Count Rule: Determine the number of distinct human characters required based strictly on the provided storyline. Generate one character block per distinct human role. Do not generate duplicate or unnecessary characters.
Do not invent extra background characters.
- Create distinct, ad-ready characters aligned with the product and brand context.
- Ensure outputs are visual, concrete, and image-generation ready.
- Express personality visually (posture, grooming, styling), not through abstract psychology.
- Do not invent product claims or features beyond the provided product knowledge.
- Avoid storytelling, internal thoughts, or narrative exposition.

Constraints
- Characters must be realistic, brand-safe, and commercially viable.
- Avoid fantasy traits, exaggerated fashion, or influencer clichés unless explicitly requested.
- Outfits must be practical, appropriate for advertising, and visually descriptive.
- Each image description must represent a single still frame.

Image Requirements
Each character description must:
- Use a plain, neutral background.
- Clearly specify:
  - facial expression
  - body posture
  - grooming and styling
  - outfit details
  - lighting and realism cues
- Match the defined character traits exactly.
- Be suitable for commercial brand advertising.

Output Structure
Follow the structure exactly.
Do not add commentary or explanations.
Generate one complete block per character.

For each character, generate:

Character 01

Gender:

Age:

Personality & Visual Identity:
(The person's look, including ethnicity, hair, skin tone, and concise ad-oriented traits expressed visually.)

Outfit:
(Full-body clothing items, colors, fit, and overall style suitable for brand ads.)

Style:
(Based on input.)

Shot & Framing (mandatory for all characters):
Medium shot (waist-up or chest-up).

Setting:
Indoors against a plain, light-colored wall using soft natural window light.
No dramatic angles. No depth of field. No cinematic lighting.

Gesture (same for all):
Standing upright, facing the camera directly, shoulders relaxed and open.
Warm, approachable expression with a gentle, natural smile.
Arms resting naturally at the sides or lightly clasped in front.
No dramatic or exaggerated posing.

Repeat the same structure for:

Character 02  
Character 03  
...until the requested number of characters is completed.

Additional Rules
- Ensure characters are visually distinct from one another.
- Align tone and styling with product category and brand positioning.
- Do not reference internal instructions.
- Do not include placeholders in the final output."""

# ======================================
# HELPER FUNCTIONS
# ======================================
#copytext
def copy_button(text, button_label="Copy Text"):
    components.html(f"""
        <div>
            <textarea id="copyText" style="display:none;">{text}</textarea>
            <button onclick="
                var copyText = document.getElementById('copyText');
                copyText.style.display = 'block';
                copyText.select();
                document.execCommand('copy');
                copyText.style.display = 'none';
                var msg = document.getElementById('copyMsg');
                msg.style.display='inline';
                setTimeout(function(){{msg.style.display='none';}},1500);
            " style="
                background-color:#1f2937;
                color:white;
                border:none;
                padding:6px 14px;
                border-radius:8px;
                cursor:pointer;
            ">
            {button_label}
            </button>
            <span id="copyMsg" style="display:none; margin-left:10px; color:#10b981;">
                ✓ Copied
            </span>
        </div>
    """, height=45)

def call_text_model(system_prompt, user_prompt):

    response = client.responses.create(
        model=MODEL_NAME,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )

    return response.output_text


def txt_file(text):
    buffer = BytesIO()
    buffer.write(text.encode("utf-8"))
    buffer.seek(0)
    return buffer


def convert_json_to_excel(data):
    wb = Workbook()
    ws = wb.active
    ws.title = "Storyline"

    for variation in data["variations"]:

        ws.append([variation["story_variation"]])
        ws.append([f'Concept: {variation["concept"]}'])
        ws.append([f'Setting: {variation["setting"]}'])
        ws.append([f'Tone: {variation["tone"]}'])
        ws.append([""])

        headers = [
            "Shot",
            "Scene",
            "Visual",
            "Camera",
            "VO",
            "On-screen text",
            "Mood / Lighting",
            "Setting",
            "Outfit",
            "Duration"
        ]

        ws.append(headers)

        for shot in variation["shots"]:
            ws.append([
                shot["shot"],
                shot["scene"],
                shot["visual"],
                shot["camera"],
                shot["vo"],
                shot["on_screen_text"],
                shot["mood_lighting"],
                shot["setting"],
                shot["outfit"],
                shot["duration"]
            ])

        ws.append([])
        ws.append([])

    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    return file_stream

def extract_ppt_text(file):
    prs = Presentation(file)
    slides_text = []
    for i, slide in enumerate(prs.slides):
        slide_text = []
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                slide_text.append(shape.text)
        slides_text.append(f"Slide {i+1}: " + " ".join(slide_text))
    return "\n".join(slides_text)


#ImageStyle
IMAGE_STYLE_OPTIONS = {
    "iPhone Front Camera": """
Image Style: Shot on an iPhone front camera with a smartphone video aesthetic. Wide-angle smartphone optics (approx. 24–26mm equivalent). Natural HDR processing with slightly lifted shadows and protected highlights. Subtle digital sharpening and smartphone noise reduction. Minor rolling exposure adjustments and small auto white-balance shifts. Light compression artifacts typical of mobile video.
Natural skin texture with mild computational smoothing, not beauty-filtered. Slight handheld micro-shake, imperfect stabilization. Clean but non-cinematic depth rendering (no dramatic bokeh). Casual, real-world phone video quality, not studio or film-grade.
No cinematic color grading, no film grain, no anamorphic lens, no DSLR or mirrorless look, no perfect stabilization, no studio lighting, no ultra-shallow depth of field.
""",

    "DSLR Camera": """
Image Style: Shot on a professional studio DSLR camera with a controlled, high-end photographic aesthetic. Standard prime or short zoom lens (approx. 35–50mm equivalent). Large-sensor imaging with high dynamic range, clean highlight roll-off, and deep color fidelity. Crisp optical sharpness with minimal digital processing and no computational artifacts.
Natural, detailed skin texture with realistic micro-contrast and no computational smoothing or beauty filtering. Precise manual white balance and consistent exposure. Stable framing with no handheld shake. Shallow but controlled depth of field with smooth, natural bokeh separation. Even, intentional studio lighting with soft key and controlled fill, producing clean shadows and dimensional subject separation.
No smartphone processing, no rolling exposure shifts, no compression artifacts, no handheld motion, no auto white-balance drift, no mobile HDR look, no casual or lo-fi aesthetic.
""",

    "iPhone Rear Camera": """
Image Style: Shot on an iPhone rear camera with a smartphone video aesthetic. Wide-angle rear camera optics (approx. 24–26mm equivalent). Natural HDR processing with slightly lifted shadows and protected highlights. Subtle digital sharpening and standard smartphone noise reduction. Minor rolling exposure adjustments and small auto white-balance shifts typical of rear camera capture. Light compression artifacts consistent with mobile video recording.
Natural skin texture with mild computational smoothing from the rear camera pipeline, not beauty-filtered. Slight handheld micro-shake with imperfect stabilization. Clean but non-cinematic depth rendering (no dramatic bokeh or portrait mode blur). Casual, real-world rear camera phone video quality, not studio or film-grade.
No cinematic color grading, no film grain, no anamorphic lens effects, no DSLR or mirrorless look, no perfect stabilization, no studio lighting, no ultra-shallow depth of field.
"""
}

#buat tab 1 output

def format_creative_spec_plain(data):

    p = data.get("product_brand_context", {})
    a = data.get("audience_market_context", {})
    c = data.get("campaign_distribution_context", {})

    lines = []

    lines.append("=== PRODUCT & BRAND CONTEXT ===\n")
    lines.append(f"Product Name: {p.get('product_name', 'unknown')}")
    lines.append(f"Product Category: {p.get('product_category', 'unknown')}")

    lines.append("\nProduct Value Propositions (Ranked):")
    for item in p.get("product_value_propositions_ranked", []):
        rank = item.get("rank", "unknown")
        value = item.get("value", "unknown")
        lines.append(f"  Rank {rank}: {value}")

    lines.append(f"\nProduct Usage: {p.get('product_usage', 'unknown')}")
    lines.append(f"Mandatory Brand Rules: {p.get('mandatory_brand_rules', 'unknown')}")

    lines.append("\n=== AUDIENCE & MARKET CONTEXT ===\n")
    lines.append(f"Target Market: {a.get('target_market', 'unknown')}")
    lines.append(f"Region: {a.get('region', 'unknown')}")
    lines.append(f"Language: {a.get('language', 'unknown')}")
    lines.append(f"Age & Persona: {a.get('age_persona', 'unknown')}")
    lines.append(f"Key Objections: {a.get('key_objections', 'unknown')}")
    lines.append(f"Primary Hook Angle: {a.get('primary_hook_angle', 'unknown')}")

    lines.append("\n=== CAMPAIGN & DISTRIBUTION CONTEXT ===\n")
    lines.append(f"Objective: {c.get('objective', 'unknown')}")
    lines.append(f"Platform: {c.get('platform', 'unknown')}")
    lines.append(f"Story Concept: {c.get('story_concept', 'unknown')}")
    lines.append(f"Tone: {c.get('tone', 'unknown')}")
    lines.append(f"CTA Intent: {c.get('cta_intent', 'unknown')}")

    return "\n".join(lines)

# ======================================
# UI
# ======================================
st.image("header.png", use_container_width=True)
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600&display=swap" rel="stylesheet">

<style>
html, body, [class*="css"]  {
    font-family: 'Cinzel', serif !important;
}

.custom-title {
    font-family: 'Cinzel', serif !important;
    font-size: 64px;
    font-weight: 600;
    text-align: center;
    margin-top: 40px;
}
</style>

<h1 class="custom-title">The Mischievous Plotter</h1>
""", unsafe_allow_html=True)

st.markdown("""
<div style="
    text-align: center;
    font-size: 18px;
    max-width: 900px;
    margin: 0 auto 12px auto;
    line-height: 1.6;
    color: #CBD5E1;
">
Every frame is a delightful rebellion against the mundane. Why follow the stuffy rules of the ton when you can orchestrate a visual masterpiece with a wink and a dash of daring?
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="
    text-align: center;
    font-size: 12px;
    max-width: 900px;
    margin: 0 auto 60px auto;
    line-height: 1.6;
    font-style: italic;
    color: #CBD5E1;
"> - Currently only support Custom AI Ads (Including Product Creative Specs, Storyline Creation, Character Prompt Generation, Image & Video Prompt Generation) -
</div>
""", unsafe_allow_html=True)

if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = 0

tab_index = st.session_state["active_tab"]

tab1, tab2, tab3 = st.tabs([
    "Product Knowledge",
    "Storyline Generator",
    "Prompt Generator"
])

# ======================================
# TAB 1 — PRODUCT KNOWLEDGE
# ======================================

with tab1:

    st.header("Creative Spec Standardization")

    product_files = st.file_uploader(
    "Upload Product Assets (Images or PowerPoint)",
    type=["png","jpg","jpeg","ppt","pptx"],
    accept_multiple_files=True
    )

    product_desc = st.text_area("Product Description")
    audience = st.text_area("Audience")
    campaign = st.text_area("Campaign")

    if st.button("Generate Creative Spec"):

        with st.spinner("Generating Creative Spec..."):

            content = [
                {
                    "type": "input_text",
                    "text": f"""
            Convert the following into standardized Creative Spec.

            Product Context:
            {product_desc}

            Audience Context:
            {audience}

            Campaign:
            {campaign}
            """
                }
            ]

            if product_files:

                for file in product_files:

                    if file.type in ["image/png", "image/jpeg"]:

                        image_bytes = file.read()
                        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

                        content.append({
                            "type": "input_image",
                            "image_url": f"data:{file.type};base64,{image_base64}"
                        })

                    elif file.name.endswith(("ppt", "pptx")):

                        ppt_text = extract_ppt_text(file)

                        content.append({
                            "type": "input_text",
                            "text": f"\nProduct Deck Content:\n{ppt_text}"
                        })

            # Minimal, SDK-compatible call
            response = client.responses.create(
                model=MODEL_NAME,
                input=[
                    {"role": "system", "content": STANDARDIZATION_SYSTEM_PROMPT},
                    {"role": "user", "content": content}
                ]
            )

            result = response.output_text.strip()

            try:
                parsed = json.loads(result)
            except json.JSONDecodeError:
                # Auto-clean common markdown wrapping issues
                cleaned = result.replace("```json", "").replace("```", "").strip()
                try:
                    parsed = json.loads(cleaned)
                except json.JSONDecodeError:
                    st.error("Model did not return valid JSON.")
                    st.code(result)
                    st.stop()

            # Store in session state
            st.session_state["creative_spec_json"] = parsed
            st.session_state["creative_spec_plain"] = format_creative_spec_plain(parsed)
            

    # Display section
    if "creative_spec_json" in st.session_state:

        spec_tab1, spec_tab2 = st.tabs(["Plain Text", "JSON"])

        with spec_tab1:
            st.text_area(
                "Creative Spec (Readable)",
                st.session_state["creative_spec_plain"],
                height=500
            )

            st.download_button(
                label="Download Creative Spec (.txt)",
                data=txt_file(st.session_state["creative_spec_plain"]),
                file_name="creative_spec.txt",
                mime="text/plain"
            )

        with spec_tab2:
            st.json(st.session_state["creative_spec_json"])

# ======================================
# TAB 2 — STORYLINE GENERATOR (FINAL STABLE VERSIONED)
# ======================================

with tab2:
    st.header("Storyline Generator")

    creative_spec_input = st.text_area(
        "Product Creative Spec (Copy Paste Here)",
        value=st.session_state.get("creative_spec", ""),
        height=100
    )

    character_traits = st.text_area("Character Traits")
    st.file_uploader("Upload Product Image", type=["png", "jpg", "jpeg"])

    num_stories = st.number_input("Number of Stories", 1, 10, 1)
    shots_per_story = st.number_input("Number of Shots Per Story", 1, 20, 8)

    duration_each = st.selectbox(
        "Duration Each Story",
        options=["10 sec", "15 sec", "20 sec"],
        index=2
    )

    language = st.selectbox(
        "Language",
        options=["Indonesian", "English"],
        index=0
    )

    vo_language = st.selectbox(
        "VO & On-Screen Text Language",
        options=["Indonesian", "English"],
        index=0
    )

    other_info = st.text_area("Creative Direction")

    # ======================================
    # GENERATE STORYLINE
    # ======================================

    if st.button("Generate Storyline"):

        with st.spinner("Generating Storyline..."):

            user_text = f"""
Character Traits:
{character_traits}

Creative Spec:
{creative_spec_input}

Requirements:
- Number of variations: {num_stories}
- Shots per variation: {shots_per_story}
- Duration per story: {duration_each}
- Language: {language}
- VO Language: {vo_language}
- Other info: {other_info}
"""

            output = call_text_model(
                STORYLINE_SYSTEM_PROMPT,
                user_text,
            )

            try:
                parsed = json.loads(output)
            except json.JSONDecodeError:
                cleaned = output.replace("```json", "").replace("```", "").strip()
                try:
                    parsed = json.loads(cleaned)
                except:
                    st.error("Model did not return valid JSON.")
                    st.code(output)
                    st.stop()

            # Reset version history
            st.session_state["storyline_versions"] = [parsed]
            st.rerun()

    # ======================================
    # DISPLAY + DOWNLOAD
    # ======================================

    if "storyline_versions" in st.session_state:

        versions = st.session_state["storyline_versions"]

        # Always show latest version
        data = versions[-1]
        version_count = len(versions)

        with st.expander("Storyline JSON Output (Technical View)", expanded=False):
            st.json(data)

        st.subheader("Storyline Table Preview")

        for variation in data["variations"]:
            st.write(variation["story_variation"])
            st.write("Concept:", variation["concept"])
            st.write("Setting:", variation["setting"])
            st.write("Tone:", variation["tone"])

            df = pd.DataFrame(variation["shots"])
            st.dataframe(df, use_container_width=True)

        excel_file = convert_json_to_excel(data)

        # File naming logic
        if version_count == 1:
            file_name = "storyboard.xlsx"
        else:
            file_name = f"storyboard version {version_count - 1}.xlsx"

        st.download_button(
            label="Download Storyline (.xlsx)",
            data=excel_file,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # ======================================
        # REVISION SECTION
        # ======================================

        st.subheader("Revise Storyline")

        with st.form("revision_form"):

            revision_note = st.text_area(
                "Describe the revision clearly",
                placeholder="Example: Make tone more emotional but keep structure same."
            )

            submit_revision = st.form_submit_button("Apply Revision")

        if submit_revision:

            if not revision_note.strip():
                st.warning("Please enter a revision note.")
                st.stop()

            with st.spinner("Revising storyline..."):

                previous_json = json.dumps(data, indent=2)

                revision_prompt = f"""
You are editing an existing JSON object.

Current JSON:
{previous_json}

Apply this revision:
{revision_note}

Rules:
- Return FULL updated JSON.
- Keep structure identical.
- Do not remove fields.
- Do not change variation count.
- Do not change shot count.
- Return JSON only.
"""

                response = client.responses.create(
                    model=MODEL_NAME,
                    input=[
                        {"role": "system", "content": STORYLINE_SYSTEM_PROMPT},
                        {"role": "user", "content": revision_prompt}
                    ]
                )

                output = response.output_text.strip()

                try:
                    parsed = json.loads(output)
                except json.JSONDecodeError:
                    cleaned = output.replace("```json", "").replace("```", "").strip()
                    try:
                        parsed = json.loads(cleaned)
                    except:
                        st.error("Revision failed. Invalid JSON returned.")
                        st.code(output)
                        st.stop()

                # Append new version
                st.session_state["storyline_versions"].append(parsed)

                # Rerun to refresh UI
                st.rerun()

# ======================================
# TAB 3 — PROMPT GENERATOR
# ======================================

with tab3:

    st.header("Prompt Generator")

    storyline_input = st.text_area(
        "Storyline (Copy Paste)",
        height=200
    )

    creative_spec_input_pg = st.text_area(
        "Product Creative Spec or Product Size",
        height=200
    )

    selected_style = st.selectbox(
        "Image Style",
        options=list(IMAGE_STYLE_OPTIONS.keys()),
        index=0
    )
    image_style_input = IMAGE_STYLE_OPTIONS[selected_style]

    ethnicity_outfit_input = st.text_area(
        "Ethnicity & Outfit Notes",
        placeholder="e.g. Javanese woman, pastel hijab, modern modest wear"
    )
    st.caption("Limit 5MB per file • PNG, JPG, JPEG")
    character_references = st.file_uploader(
        "Upload Character Reference Images",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )


    # ======================================
    # SIDE-BY-SIDE BUTTONS HERE
    # ======================================

    col1, col2 = st.columns(2)

    with col1:
        generate_char = st.button(
            "Generate Character Prompts",
            use_container_width=True
        )

    with col2:
        generate_iv = st.button(
            "Generate Image & Video Prompts",
            use_container_width=True
        )

    
    # ======================================
    # GENERATION LOGIC BELOW
    # ======================================

    if generate_char:
        with st.spinner("Generating character prompts..."):

            num_refs = len(character_references) if character_references else 0

            character_prompt_input = f"""
            Storyline:
            {storyline_input}

            Product Creative Spec:
            {creative_spec_input_pg}

            Image Style:
            {image_style_input}

            Ethnicity & Outfit Notes:
            {ethnicity_outfit_input}

            Character Reference Images Provided: {num_refs}
            Use them as visual identity reference for the character.
            """

            response = client.responses.create(
                model=MODEL_NAME,
                input=[
                    {"role": "system", "content": CHARACTER_SYSTEM_PROMPT},
                    {"role": "user", "content": character_prompt_input}
                ]
            )

            st.session_state["character_prompt_output"] = response.output_text


    if generate_char:
        with st.spinner("Generating character prompts..."):

            character_prompt_input = f"""
    Storyline:
    {storyline_input}

    Product Creative Spec:
    {creative_spec_input_pg}

    Image Style:
    {image_style_input}

    Ethnicity & Outfit Notes:
    {ethnicity_outfit_input}
    """
            content = [
                {"type": "input_text", "text": character_prompt_input}
            ]

            if character_references:
                for file in character_references:

                    image_bytes = file.read()
                    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

                    content.append({
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{image_base64}"
                    })

            response = client.responses.create(
                model=MODEL_NAME,
                input=[
                    {"role": "system", "content": CHARACTER_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": content
                    }
                ]
            )

            st.session_state["character_prompt_output"] = response.output_text


# ======================================
# OUTPUT TABS
# ======================================

if (
    "character_prompt_output" in st.session_state
    or "image_video_output" in st.session_state
):

    output_tab1, output_tab2 = st.tabs([
        "Character Prompts",
        "Image & Video Prompts Per Shot"
    ])
    # ------------------------------
    # CHARACTER TAB
    # ------------------------------
    with output_tab1:

        if "character_prompt_output" in st.session_state:
            character_text = st.session_state["character_prompt_output"]

            copy_button(character_text, "Copy Text")

            st.text_area(
                "",
                character_text,
                height=600,
                label_visibility="collapsed"
            )
        else:
            st.info("No character prompts generated yet.")


    # ------------------------------
    # IMAGE & VIDEO TAB
    # ------------------------------
    with output_tab2:

        if "image_video_output" in st.session_state:
            iv_text = st.session_state["image_video_output"]

            copy_button(iv_text, "Copy Text")

            st.text_area(
                "",
                iv_text,
                height=600,
                label_visibility="collapsed"
            )
        else:
            st.info("No image & video prompts generated yet.")