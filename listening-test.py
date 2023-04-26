import os
import json
import time
import random
import boto3

import streamlit as st
from streamlit_javascript import st_javascript

st.set_page_config(page_title="AI-Generated Drum Pattern Evaluation")


def set_page_styles():
    hide_header_style = """
            <style>
            header {visibility: hidden;}
            </style>
            """
    hide_streamlit_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                </style>
                """
    content_width_style = """
                <style>
                .block-container {max-width: 1000px !important;}
                </style>
                """
    st.markdown(hide_header_style, unsafe_allow_html=True)
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    st.markdown(content_width_style, unsafe_allow_html=True)

    # Reduce padding at the top of the page
    st.markdown("""
            <style>
                   .block-container {
                        margin-top: -5rem;
                        padding-top: 2rem;
                        padding-bottom: 0rem;
                    }
            </style>
            """, unsafe_allow_html=True)


def show_intro_text():
    st.title('AI-Generated Drum Pattern Evaluation')

    st.write(
        "This is an open survey to evaluate drum patterns generated by various artificial intelligence methods.")
    st.write(
        "It is being conducted by [Taylor Peer](https://www.linkedin.com/in/taylorpeer/) as part of a master's thesis in Software Engineering at the TU Wien in Vienna, Austria.")
    st.write(
        "To participate in the survey, please fill out the fields below. Then listen to the audio files at the bottom of the page and rate them according to the listed criteria.")

    st.markdown("""---""")


def get_basic_user_info():
    st.header('Basic Information')

    st.write(
        "The information collected here helps give context to the results of the survey and is used solely for research purposes. Feel free to leave these fields blank if you prefer.")

    age = st.text_input('Your Age (optional)', '')
    gender = st.radio("Gender (optional)",
                      ('Male', 'Female', 'Other/diverse', 'Rather not say'), index=3)
    background = st.radio("Musical background (optional)",
                          ('None', 'Hobby musician or producer', 'Professional musician or producer', 'Rather not say'),
                          index=3)
    st.write(
        "If you'd like to receive the results of this survey once it's completed, please enter your email address below:")
    email = st.text_input('Email Address (optional)', '')

    st.markdown("""---""")
    return {"age": age, "gender": gender, "background": background, "email": email}


def get_client_ip():
    url = 'https://api.ipify.org?format=json'
    script = (f'await fetch("{url}").then('
              'function(response) {'
              'return response.json();'
              '})')

    try:
        result = st_javascript(script)
        if isinstance(result, dict) and 'ip' in result:
            return result['ip']
    except:
        return "unable to fetch IP"


def populate_audio():
    for root, dirs, files in os.walk("audio"):
        for file in files:
            if file.endswith(".wav"):
                yield os.path.join(root, file)


def select_audio():
    update_path = False

    update_path = update_path or "selected_audio_path" not in st.session_state
    update_path = update_path or st.session_state.selected_audio_path is None
    update_path = update_path or "prev_genre" in st.session_state and st.session_state.prev_genre != selected_genre

    if update_path:
        audio_files = list(populate_audio())
        if selected_genre != "Any Genre":
            audio_files = [audio_file for audio_file in audio_files if audio_file.split("/")[1] == selected_genre]
        selected_audio_path = random.choice(audio_files)
        st.session_state.selected_audio_path = selected_audio_path
        st.session_state.prev_genre = selected_genre


ACCESS_KEY = os.environ['AWS_ACCESS_KEY']
SECRET_KEY = os.environ['AWS_SECRET_KEY']
BUCKET = os.environ['BUCKET'] if 'BUCKET' in os.environ else 'dev'
aws_client = boto3.client('s3', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)

ip = get_client_ip()
set_page_styles()
show_intro_text()
st.session_state.user_info = get_basic_user_info()
if "ip_address" not in st.session_state.user_info:
    st.session_state.user_info["ip_address"] = ip if ip is not None else round(time.time() * 1000)

st.header('Evaluation')

st.write(
    "Below you can listen to recordings of drum patterns. Each pattern was either written by a human composer or generated by an AI algorithm. All patterns have been converted to music notation and reproduced via a synthetic drum kit to obscure their original source.")
st.write(
    "After submitting your ratings for a drum pattern, the source (human or AI) will be revealed and you may rate another pattern. Patterns are selected at random, though you may filter by specific genres of music (for instance, those you are most familiar with). Please rate as many drum patterns as you wish.")

likert_values = ["Strongly disagree", "Somewhat disagree", "Somewhat agree", "Strongly agree"]

questions = [
    "The recording of the drum pattern sounds like an expressive human performance:",
    "The drum pattern plays without any technical glitches (e.g. sudden pauses):",
    "Overall I find the drum pattern interesting and pleasing to listen to:"
]

if "q1" not in st.session_state:
    for question_index in [1, 2, 3, 4, 5]:
        st.session_state["q{}".format(question_index)] = {}
        response_indices = ["0", "1", "2", "3", "4"]
        if question_index == 1:
            response_indices = ["0", "1", "2"]
        for response_index in response_indices:
            st.session_state["q{}".format(question_index)][str(response_index)] = 0
    st.session_state.feedback = ""
    st.session_state.score = ""
    st.session_state.input_disabled = False
    st.session_state.submit_button_text = "Submit"
    st.session_state.ratings = 0
    st.session_state.correct = 0


def q_change(question_index, pos_index):
    reset(question_index)
    st.session_state["q{}".format(question_index)][str(pos_index)] = 1


def reset(for_question=None):

    # Check if something was selected
    nothing_selected = True
    for question_index in [1, 2, 3, 4, 5]:
        response_indices = ["0", "1", "2", "3", "4"]
        if question_index == 1:
            response_indices = ["0", "1", "2"]
        for response_index in response_indices:
            if st.session_state["q{}".format(question_index)][str(response_index)] > 0:
                nothing_selected = False
    if for_question is None and st.session_state.submit_button_text == "Submit" and nothing_selected:
        st.session_state.score = "Please answer the above questions before submitting."
        return

    correct_on1 = False
    correct_on2 = False
    unsure = True if st.session_state.q1["2"] or (
            st.session_state.q1["0"] == 0 and st.session_state.q1["1"] == 0) else False
    if source == "training" and st.session_state.q1["0"]:
        correct_on1 = True
    elif source == "generated" and st.session_state.q1["1"]:
        correct_on2 = True

    if for_question is None:

        with placeholder:
            with st.spinner("Submitting rating, hold on for a second..."):

                if st.session_state.submit_button_text == "Submit":
                    if not unsure:
                        st.session_state.ratings = st.session_state.ratings + 1
                        if correct_on1 or correct_on2:
                            st.session_state.feedback = "Correct! "
                            st.session_state.correct = st.session_state.correct + 1
                        elif not unsure:
                            st.session_state.feedback = "Incorrect! "

                    if st.session_state.ratings > 0:
                        percentage = round((st.session_state.correct / st.session_state.ratings) * 100)
                        score_message = "You correctly identified {} out of {} ({}%) human-vs-AI generated drum patterns.  \n Press *Next* to evaluate another.".format(
                            st.session_state.correct, st.session_state.ratings, percentage)
                    else:
                        score_message = "Press *Next* to evaluate another."

                    if not unsure:
                        if source == "training":
                            st.session_state.feedback += "This drum \npattern was \nhuman-composed"
                        elif source == "generated":
                            st.session_state.feedback += "This drum \npattern was \nAI-generated"
                    else:
                        if source == "training":
                            st.session_state.feedback += "This drum pattern was \nhuman-composed"
                        elif source == "generated":
                            st.session_state.feedback += "This drum pattern was \nAI-generated"
                    st.session_state.score = score_message
                    st.session_state.submit_button_text = "Next"
                    st.session_state.input_disabled = True
                    submit()
                else:
                    st.session_state.feedback = ""
                    st.session_state.score = ""
                    st.session_state.submit_button_text = "Submit"
                    st.session_state.input_disabled = False
                    st.session_state.selected_audio_path = None

    # Reset all checkboxes
    for question_index in [1, 2, 3, 4, 5]:
        if for_question is not None:
            if for_question != question_index:
                continue
        q = "q{}".format(question_index)
        response_indices = ["0", "1", "2", "3", "4"]
        if question_index == 1:
            response_indices = ["0", "1", "2"]
        for response_index in response_indices:
            st.session_state[q][response_index] = 0


audio_files = list(populate_audio())
genres = tuple(list(set([audio_file.split("/")[1] for audio_file in audio_files])) + ["Any Genre"])
st.write("Select a genre of drum patterns to evaluate or select *Any Genre* for a random selection:")
selected_genre = st.radio(label="", options=genres, index=len(genres) - 1, on_change=select_audio,
                          label_visibility="collapsed")
select_audio()
path_components = st.session_state.selected_audio_path.split("/")
genre = path_components[1]
source = path_components[2]
song_id = path_components[3]
audio_file = open(st.session_state.selected_audio_path, 'rb')
audio_bytes = audio_file.read()

st.write("Listen to the audio file before answering the questions below:")
st.audio(audio_bytes, format='audio/wav')

# QUESTION 1
st.write("Is this drum pattern human-composed or AI-generated?")
q1_values = ["Human-composed", "AI-generated", "Unsure"]
columns = st.columns([1, 1, 1, 1])
for q1_index, q1_value in enumerate(q1_values):
    with columns[0]:
        st.checkbox(q1_value,
                    key="q1_{}".format(q1_index),
                    value=st.session_state.q1[str(q1_index)],
                    disabled=st.session_state.input_disabled,
                    on_change=q_change,
                    args=(1, q1_index,))
with columns[1]:
    st.text(st.session_state.feedback)

# QUESTION 2
st.text("\n")
st.write("This drum pattern is representative of the *{}* genre:".format(genre))
for q2_index, (q2_value, col) in enumerate(zip(likert_values, st.columns([1, 1, 1, 1]))):
    with col:
        st.checkbox(q2_value,
                    key="q2_{}".format(q2_index),
                    value=st.session_state.q2[str(q2_index)],
                    disabled=st.session_state.input_disabled,
                    on_change=q_change, args=(2, q2_index,))

for question_index, question in enumerate(questions):
    question_index = question_index + 3  # TODO
    st.text("\n")
    st.write(question)
    for index, (value, col) in enumerate(zip(likert_values, st.columns([1, 1, 1, 1]))):
        with col:
            st.checkbox(value,
                        key="q{}_{}".format(question_index, index),
                        value=st.session_state["q{}".format(question_index)][str(index)],
                        disabled=st.session_state.input_disabled,
                        on_change=q_change, args=(question_index, index,))

st.text("\n")

st.write(st.session_state.score)
st.button(st.session_state.submit_button_text, on_click=reset)
placeholder = st.empty()


def get_question_response(question_index):
    response_indices = ["0", "1", "2", "3", "4"]
    if question_index == 1:
        response_indices = ["0", "1", "2"]
    for response_index in response_indices:
        question_state = st.session_state["q{}".format(question_index)][str(response_index)]
        if question_state > 0:
            return response_index
    return -1


def submit():
    current_time_ms = round(time.time() * 1000)
    data_dict["timestamp"] = current_time_ms
    data_dict["num_ratings"] = st.session_state.ratings
    data_dict["num_correct"] = st.session_state.correct

    try:
        aws_client.put_object(
            Bucket='listening-test-results',
            # TODO bucket as environment variable
            Key="dev/{}-{}.json".format(st.session_state.user_info["ip_address"].replace(".", "_"), current_time_ms),
            Body=json.dumps(data_dict, indent=2, default=str)
        )
    except:
        st.session_state.score = "Failed to store evaluation results!"


data_dict = {
    "filename": st.session_state.selected_audio_path,
    "reviewer": {
        "age": st.session_state.user_info["age"],
        "gender": st.session_state.user_info["gender"],
        "background": st.session_state.user_info["background"],
        "email": st.session_state.user_info["email"],
        "ip": st.session_state.user_info["ip_address"]
    },
    "ratings": {
        "human-or-ai": get_question_response(1),
        "representative-of-genre": get_question_response(2),
        "expressive": get_question_response(3),
        "free-of-glitches": get_question_response(4),
        "overall": get_question_response(5)
    }
}
