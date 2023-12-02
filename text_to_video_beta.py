import requests
import json

def create_a_talk(word, api_key):
    url = "https://api.d-id.com/talks"

    payload = {
    "script": {
        "type": "text",
        "subtitles": "false",
        "provider": {
            "type": "microsoft",
            "voice_id": "zh-CN-XiaoxiaoNeural"
        },
        "ssml": "false",
        "input": word
    },
    "config": {
        "fluent": "false",
        "pad_audio": "0.0"
    },
    "source_url": "https://create-images-results.d-id.com/api_docs/assets/noelle.jpeg"
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": "Basic "+ api_key
    }

    response = requests.post(url, json=payload, headers=headers)
    response_json = json.loads(response.text)
    talk_id = response_json['id']
    # return talk_id
    
    url = "https://api.d-id.com/talks/"+talk_id
    headers = {
        "accept": "application/json",
        "authorization": "Basic "+api_key
    }
    while True:
        response = requests.get(url, headers=headers)
        response_json = json.loads(response.text)
        status = response_json['status']
        if status == 'done':
            break
    
    result_url = response_json['result_url']

    return result_url
    
