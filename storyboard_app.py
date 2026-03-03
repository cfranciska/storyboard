import streamlit as st
import pandas as pd
from openpyxl import Workbook
from io import BytesIO
from openai import OpenAI
import json
import streamlit.components.v1 as components

# ======================================
# CONFIG
# ======================================

st.set_page_config(page_title="AI Storyboard Builder", layout="wide")

API_KEY = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=API_KEY)

MODEL_NAME = "gpt-5-mini"

# ======================================
# SYSTEM PROMPTS
# ======================================

STANDARDIZATION_SYSTEM_PROMPT = """
You are a standardization engine.
Return only the Creative Spec Schema exactly as requested.
Do not add commentary.
Do not invent claims.
If missing info, use "unknown".
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

    product_desc = st.text_area("Product Description")
    audience = st.text_area("Audience")
    campaign = st.text_area("Campaign")

    if st.button("Generate Creative Spec"):

        with st.spinner("Generating Creative Spec..."):

            user_prompt = f"""
Convert the following into standardized Creative Spec.

Product Context: {product_desc}
Audience Context: {audience}
Campaign: {campaign}
"""

            result = call_text_model(
                STANDARDIZATION_SYSTEM_PROMPT,
                user_prompt
            )

            st.session_state["creative_spec"] = result

    if "creative_spec" in st.session_state:

        st.text_area(
            "Creative Spec Output",
            st.session_state["creative_spec"],
            height=400
        )

        st.download_button(
            label="Download Creative Spec (.txt)",
            data=txt_file(st.session_state["creative_spec"]),
            file_name="creative_spec.txt",
            mime="text/plain"
        )

# ======================================
# TAB 2 — STORYLINE GENERATOR
# ======================================

with tab2:

    st.header("Storyline Generator")

    creative_spec_input = st.text_area(
        "Product Creative Spec (Copy Paste Here)",
        value=st.session_state.get("creative_spec", ""),
        height=100
    )

    character_traits = st.text_area("Character Traits")

    # Keep image upload for UI reference only
    st.file_uploader("Upload Product Image", type=["png", "jpg", "jpeg"])

    num_stories = st.number_input("Number of Stories", 1, 10, 1)
    shots_per_story = st.number_input("Number of Shots Per Story", 1, 20, 8)
    duration_each = st.selectbox(
    "Duration Each Story",
    options=["10 sec", "15 sec", "20 sec"],
    index=2  # default = 20 sec
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
                st.session_state["storyline_versions"] = [parsed]
                st.session_state["active_version_index"] = 0
            except:
                st.error("Model did not return valid JSON. Please regenerate.")
                st.stop()

    if "storyline_json" in st.session_state:

        versions = st.session_state["storyline_versions"]
        active_index = st.session_state["active_version_index"]

        # ==============================
        # STEP 3 — VERSION SELECTOR HERE
        # ==============================

        version_labels = [
            f"Version {i+1}" for i in range(len(versions))
        ]

        selected_version = st.selectbox(
            "Select Version",
            options=range(len(versions)),
            format_func=lambda i: version_labels[i],
            index=active_index
        )

        st.session_state["active_version_index"] = selected_version
        data = versions[selected_version]

        # ==============================
        # THEN CONTINUE NORMAL RENDERING
        # ==============================

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

        st.download_button(
            label="Download Storyline (.xlsx)",
            data=excel_file,
            file_name="storyine.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # ======================================
    # MINOR REVISION SECTION
    # ======================================

        st.subheader("Request Minor Revision")

        revision_note = st.text_area(
            "Describe the minor revision clearly",
            placeholder="Example: Make tone more emotional but keep structure same."
        )

        if st.button("Revise Storyline", disabled=not revision_note.strip()):

            with st.spinner("Revising storyline..."):

                previous_json = json.dumps(
                    st.session_state["storyline_json"],
                    indent=2
                )

                revision_prompt = f"""
    Here is the current storyline JSON:

    {previous_json}

    Apply the following minor revision:
    {revision_note}

    Rules:
    - Keep JSON structure identical.
    - Do NOT remove fields.
    - Do NOT change number of variations.
    - Do NOT change number of shots.
    - Only modify what is required.
    - Return valid JSON only.
    """

                response = client.responses.create(
                    model=MODEL_NAME,
                    input=[
                        {"role": "system", "content": STORYLINE_SYSTEM_PROMPT},
                        {"role": "user", "content": revision_prompt}
                    ]
                )

                output = response.output_text

                try:
                    parsed = json.loads(output)
                    st.session_state["storyline_versions"].append(parsed)
                    st.session_state["active_version_index"] = len(st.session_state["storyline_versions"]) - 1
                    st.rerun()
                except:
                    st.error("Revision failed. Invalid JSON returned.")
                    st.stop()

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

            response = client.responses.create(
                model=MODEL_NAME,
                input=[
                    {"role": "system", "content": CHARACTER_SYSTEM_PROMPT},
                    {"role": "user", "content": character_prompt_input}
                ]
            )

            st.session_state["character_prompt_output"] = response.output_text


    if generate_iv:
        with st.spinner("Generating image & video prompts..."):

            iv_prompt_input = f"""
Storyline:
{storyline_input}

Product Creative Spec:
{creative_spec_input_pg}

Image Style:
{image_style_input}
"""

            response = client.responses.create(
                model=MODEL_NAME,
                input=[
                    {"role": "system", "content": IMAGE_VIDEO_SYSTEM_PROMPT},
                    {"role": "user", "content": iv_prompt_input}
                ]
            )

            st.session_state["image_video_output"] = response.output_text

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