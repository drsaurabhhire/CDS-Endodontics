import gradio as gr
import re
import json

# ===============================
# RULE ENGINE (UNCHANGED CORE)
# ===============================

def structured_process_input(
    age,
    tooth,
    endo_ice,
    lingering,
    caries,
    prev_init,
    prev_treated,
    control_tooth,
    percussion,
    swelling,
    sinus,
    radiolucency,
    radiopacity
):

    reasoning = []
    pulp = ""
    apical = ""
    treatment = ""
    cdt = ""

    # ---- PULPAL DIAGNOSIS ----

    if prev_treated:
        pulp = "Previously Treated"
        reasoning.append("Previously completed RCT identified.")

    elif prev_init:
        pulp = "Previously Initiated Therapy"
        reasoning.append("Root canal therapy previously initiated.")

    elif endo_ice == "Positive":
        if lingering:
            pulp = "Symptomatic Irreversible Pulpitis"
            reasoning.append("Endo ice positive with lingering pain.")
        else:
            if caries:
                pulp = "Asymptomatic Irreversible Pulpitis"
                reasoning.append("Vital pulp with caries into pulp.")
            else:
                pulp = "Reversible Pulpitis"
                reasoning.append("Vital pulp without pulp exposure.")

    elif endo_ice == "Negative":
        if control_tooth:
            pulp = "Pulp Necrosis"
            reasoning.append("No response to endo ice; control tooth normal.")
        else:
            pulp = "Inconclusive — Further Testing Required"
            reasoning.append("Control tooth non-responsive.")

    else:
        pulp = "Normal Pulp"

    # ---- APICAL DIAGNOSIS ----

    if percussion:
        if swelling:
            apical = "Acute Apical Abscess"
            reasoning.append("Percussion pain with swelling.")
        else:
            apical = "Symptomatic Apical Periodontitis"
            reasoning.append("Percussion pain without swelling.")
    else:
        if sinus:
            apical = "Chronic Apical Abscess"
            reasoning.append("Sinus tract present.")
        elif radiolucency:
            apical = "Asymptomatic Apical Periodontitis"
            reasoning.append("Periapical radiolucency detected.")
        elif radiopacity:
            apical = "Condensing Osteitis"
            reasoning.append("Periapical radiopacity detected.")
        else:
            apical = "Normal Apical Tissues"
            reasoning.append("No apical findings.")

    # ---- TREATMENT MAPPING ----

    treatment_map = {
        "Normal Pulp": "No treatment",
        "Reversible Pulpitis": "Remove irritant + restoration",
        "Symptomatic Irreversible Pulpitis": "Root canal therapy",
        "Asymptomatic Irreversible Pulpitis": "Root canal therapy",
        "Pulp Necrosis": "Root canal therapy",
        "Previously Initiated Therapy": "Complete root canal therapy",
        "Previously Treated": "Monitor or retreat if symptomatic"
    }

    treatment = treatment_map.get(pulp, "Further evaluation required")

    cdt_map = {
        "Root canal therapy": "D3310 / D3320 / D3330",
        "Complete root canal therapy": "D3310 / D3320 / D3330",
        "Remove irritant + restoration": "Restorative CDT Code"
    }

    cdt = cdt_map.get(treatment, "N/A")

    fhir_output = {
        "resourceType": "DiagnosticReport",
        "subject": {"reference": f"Patient/{age}"},
        "tooth": tooth,
        "pulpDiagnosis": pulp,
        "apicalDiagnosis": apical,
        "treatmentPlan": treatment
    }

    return pulp, apical, treatment, cdt, " | ".join(reasoning), json.dumps(fhir_output, indent=2)


# ===============================
# NLP EXTRACTION LAYER
# ===============================

def extract_from_text(text):

    text = text.lower()

    age_match = re.search(r'(\d{1,3})\s*year', text)
    age = int(age_match.group(1)) if age_match else None

    tooth_match = re.search(r'tooth\s*#?(\d{1,2})', text)
    tooth = int(tooth_match.group(1)) if tooth_match else None

    endo_ice = "Positive" if "endo ice positive" in text else \
                "Negative" if "endo ice negative" in text else None

    lingering = "lingering" in text
    caries = "caries" in text and "pulp" in text
    prev_init = "previously initiated" in text
    prev_treated = "previously treated" in text
    control = "control tooth positive" in text

    percussion = "percussion positive" in text or "percussion pain" in text
    swelling = "swelling" in text
    sinus = "sinus tract" in text
    radiolucency = "radiolucency" in text
    radiopacity = "radiopacity" in text

    required = [tooth, endo_ice]

    if None in required:
        return "Insufficient Clinical Data", "", "", "", "Missing required diagnostic elements.", ""

    return structured_process_input(
        age,
        tooth,
        endo_ice,
        lingering,
        caries,
        prev_init,
        prev_treated,
        control,
        percussion,
        swelling,
        sinus,
        radiolucency,
        radiopacity
    )


# ===============================
# UI
# ===============================

with gr.Blocks() as demo:

    gr.Markdown("# CDS – Endodontics")

    mode = gr.Radio(["Structured Input", "Clinical Summary (NLP Mode)"], value="Structured Input")

    summary_box = gr.Textbox(label="Clinical Summary (NLP Mode)", visible=False)

    age_input = gr.Number(label="Age")
    tooth_input = gr.Dropdown([i for i in range(1,33)], label="Tooth")
    endo_ice_input = gr.Dropdown(["Positive", "Negative"], label="Endo Ice Test")
    lingering_input = gr.Checkbox(label="Lingering Pain")
    caries_input = gr.Checkbox(label="Caries into pulp")
    prev_init_input = gr.Checkbox(label="Previously Initiated Therapy")
    prev_treated_input = gr.Checkbox(label="Previously Treated")
    control_input = gr.Checkbox(label="Control Tooth Positive")
    percussion_input = gr.Checkbox(label="Percussion Pain")
    swelling_input = gr.Checkbox(label="Swelling")
    sinus_input = gr.Checkbox(label="Sinus Tract")
    radiolucency_input = gr.Checkbox(label="Radiolucency")
    radiopacity_input = gr.Checkbox(label="Radiopacity")

    output_pulp = gr.Textbox(label="Pulpal Diagnosis")
    output_apical = gr.Textbox(label="Apical Diagnosis")
    output_treatment = gr.Textbox(label="Treatment Plan")
    output_cdt = gr.Textbox(label="CDT Code")
    output_reasoning = gr.Textbox(label="Clinical Reasoning")
    output_fhir = gr.Code(language="json")

    def switch_mode(selected):
        return gr.update(visible=(selected == "Clinical Summary (NLP Mode)"))

    mode.change(switch_mode, inputs=mode, outputs=summary_box)

    def run(mode, summary, *structured_inputs):
        if mode == "Clinical Summary (NLP Mode)":
            return extract_from_text(summary)
        else:
            return structured_process_input(*structured_inputs)

    btn = gr.Button("Run CDS")

    btn.click(
        run,
        inputs=[mode, summary_box,
                age_input, tooth_input, endo_ice_input,
                lingering_input, caries_input,
                prev_init_input, prev_treated_input,
                control_input, percussion_input,
                swelling_input, sinus_input,
                radiolucency_input, radiopacity_input],
        outputs=[output_pulp, output_apical, output_treatment,
                 output_cdt, output_reasoning, output_fhir]
    )

demo.launch(server_name="0.0.0.0", server_port=7860)
