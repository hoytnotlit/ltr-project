import xml.etree.ElementTree as ET
import timeit
import json
import requests
import time
import sys
import os.path

# Code for Sparv-tagging modified from given example 

# URL to the Sparv 2 API:
sparv_url = "https://ws.spraakbanken.gu.se/ws/sparv/v2/"

# Optional settings, specifying what analysis should be done (in this case compound analysis only):
# Check https://ws.spraakbanken.gu.se/ws/sparv/v2/#settings for more info
sparv_settings = json.dumps({
    "corpus": "Korpusnamn",
    "lang": "sv",
    "textmode": "plain",
    "positional_attributes": {
        "dependency_attributes":["ref","dephead","deprel"],
        "lexical_attributes": [
            "pos",
            "msd",
            "lemma"
        ]
    },
    "text_attributes": {
        "readability_metrics": [
            "lix",
            "ovix",
            "nk"
        ]
    }
})

query_parameters = {"text": None, "settings": sparv_settings}

# send request to Sparv API
def sparv_req(text):
    query_parameters = {"text": text, "settings": sparv_settings}
    response = requests.get(sparv_url, params=query_parameters)
    return response.text

# parse xml response
def get_sentence_pos(tagged_sentence):
    root = ET.fromstring(tagged_sentence)
    word_tags = root.findall("./corpus/text/paragraph/sentence/")
    return [{'deprel': wt.attrib['deprel'], 'msd': wt.attrib['msd']} for wt in word_tags]

# load data for corruption
def load_clean_data(file_path='leo_coctaill.xml'):
    tree = ET.parse(file_path)
    root = tree.getroot()
    return [" ".join([word.text for word in sent]) for sent in root]

# corrupt data and save corrupted sentences in text file
def corrupt_data(clean_data):
    subj_tags = ['SS', 'SP', 'ES', 'FS'] # labels from https://cl.lingfil.uu.se/~nivre/swedish_treebank/dep.html
    start_time = timeit.default_timer()
    prevelapsed = 0 
    start_i = 0

    if os.path.isfile('corrupted.txt'):
        with open('corrupted.txt', 'r') as f:
            file_lines = f.readlines()
            if len(file_lines) > 0:
                start_i = int(file_lines[-1].split("\t")[0]) + 1

    with open('corrupted.txt', 'a+') as corrupted_data:
        for i, sentence in enumerate(clean_data[start_i:], start_i):
            elapsed = timeit.default_timer() - start_time
            
            print(f"\rprocessing sentence {i} / {len(clean_data)} time elapsed: {elapsed}", end="")
            
            try:
                tagged = sparv_req(sentence)
                prevelapsed = elapsed
            except:
                print("Unexpected error:", sys.exc_info()[0])
                time.sleep(60)
                continue
            tagged_dict = get_sentence_pos(tagged)
            
            # NOTE: only one corruption is applied per sentence

            # find subjects in sentence
            sent_subjs = [i for i, item in enumerate(tagged_dict) if 'SUB' in item['msd']]
            sentence_split = sentence.split()

            # case: subject has already been mentioned
            # NOTE: not sure if this is the best way to check if subjects are same
            if len(sent_subjs) == 2 and sentence_split[sent_subjs[0]].lower() == sentence_split[sent_subjs[1]].lower():
                del sentence_split[sent_subjs[1]] # remove the second occurence of the subject
                corrupted_data.write(f'{i}\t{" ".join(sentence_split)}\n')
                continue

            # case: vad som
            # simply check for "vad som" - deprel label of som seems to be Unclassifiable grammatical function
            if "vad som" in sentence:
                som_indices = [i for i, x in enumerate(sentence_split) if x == "som"]
                som_index = som_indices[0]
                # check that "som" follows "vad" e.g in sentences like "Människor som gör vad som helst"
                if len(som_indices) > 1:
                    for i in som_indices:
                        if sentence_split[som_index-1].lower() == "vad":
                            break
                        som_index = i
                del sentence_split[sentence_split.index("som")]
                corrupted_data.write(f'{i}\t{" ".join(sentence_split)}\n')
                continue

            # case: drop prounoun subject
            # SS(PN) MS .... -> MS ....
            for sub in sent_subjs:
                if 'PN' in tagged_dict[sub]['msd'] and (sub + 1) < len(tagged_dict) and 'VB' in tagged_dict[sub + 1]['msd']:
                    del sentence_split[sub]
                    # capitalise new first token
                    if sub == 0:
                        sentence_split[0] = sentence_split[0].capitalize()
                    corrupted_data.write(f'{i}\t{" ".join(sentence_split)}\n')
                    break

if __name__ == "__main__":
    clean_data = load_clean_data()
    corrupt_data(clean_data)