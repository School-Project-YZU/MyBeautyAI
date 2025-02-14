from argparse import ArgumentParser
from age_gender_detection_live import *
import time
from pathlib import Path
import cv2
import torch
import torch.backends.cudnn as cudnn
from numpy import random

from models.experimental import attempt_load
from utils.datasets import LoadStreams, LoadImages
from utils.general import check_img_size, check_imshow, non_max_suppression, apply_classifier, \
    scale_coords, xyxy2xywh, strip_optimizer, set_logging, increment_path
from utils.plots import plot_one_box
from utils.torch_utils import select_device, load_classifier, time_synchronized, TracedModel
import openai
from read_csv_value import choose_product
from text_to_video_beta import *

import base64
import json

from flask import Flask, render_template, send_file, request, jsonify
import webbrowser
import openai
import azure.cognitiveservices.speech as speechsdk

result_url = ''

def detect(save_img=False):
    source, weights, view_img, save_txt, imgsz, trace = opt.source, opt.weights, opt.view_img, opt.save_txt, opt.img_size, not opt.no_trace
    save_img = not opt.nosave and not source.endswith('.txt')  # save inference images
    webcam = source.isnumeric() or source.endswith('.txt') or source.lower().startswith(
        ('rtsp://', 'rtmp://', 'http://', 'https://'))

    # Directories
    save_dir = Path(increment_path(Path(opt.project) / opt.name, exist_ok=opt.exist_ok))  # increment run
    (save_dir / 'labels' if save_txt else save_dir).mkdir(parents=True, exist_ok=True)  # make dir

    # Initialize
    set_logging()
    device = select_device(opt.device)
    half = device.type != 'cpu'  # half precision only supported on CUDA

    # Load model
    model = attempt_load(weights, map_location=device)  # load FP32 model
    stride = int(model.stride.max())  # model stride
    imgsz = check_img_size(imgsz, s=stride)  # check img_size

    if trace:
        model = TracedModel(model, device, opt.img_size)

    if half:
        model.half()  # to FP16

    # Second-stage classifier
    classify = False
    if classify:
        modelc = load_classifier(name='resnet101', n=2)  # initialize
        modelc.load_state_dict(torch.load('weights/resnet101.pt', map_location=device)['model']).to(device).eval()

    # Set Dataloader
    vid_path, vid_writer = None, None
    if webcam:
        view_img = check_imshow()
        cudnn.benchmark = True  # set True to speed up constant image size inference
        dataset = LoadStreams(source, img_size=imgsz, stride=stride)
    else:
        dataset = LoadImages(source, img_size=imgsz, stride=stride)

    # Get names and colors
    names = model.module.names if hasattr(model, 'module') else model.names
    colors = [[random.randint(0, 255) for _ in range(3)] for _ in names]

    # Run inference
    if device.type != 'cpu':
        model(torch.zeros(1, 3, imgsz, imgsz).to(device).type_as(next(model.parameters())))  # run once
    old_img_w = old_img_h = imgsz
    old_img_b = 1

    t0 = time.time()
    results_wrinkle = []  # 放置結果
    count_1 = 0  # 計算次數
    for path, img, im0s, vid_cap in dataset:
        if count_1 == 20:
            break
        img = torch.from_numpy(img).to(device)
        img = img.half() if half else img.float()  # uint8 to fp16/32
        img /= 255.0  # 0 - 255 to 0.0 - 1.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)

        # Warmup
        if device.type != 'cpu' and (
                old_img_b != img.shape[0] or old_img_h != img.shape[2] or old_img_w != img.shape[3]):
            old_img_b = img.shape[0]
            old_img_h = img.shape[2]
            old_img_w = img.shape[3]
            for i in range(3):
                model(img, augment=opt.augment)[0]

        # Inference
        t1 = time_synchronized()
        with torch.no_grad():  # Calculating gradients would cause a GPU memory leak
            pred = model(img, augment=opt.augment)[0]
        t2 = time_synchronized()

        # Apply NMS
        pred = non_max_suppression(pred, opt.conf_thres, opt.iou_thres, classes=opt.classes, agnostic=opt.agnostic_nms)
        t3 = time_synchronized()

        # Apply Classifier
        if classify:
            pred = apply_classifier(pred, modelc, img, im0s)

        # Process detections
        for i, det in enumerate(pred):  # detections per image
            if webcam:  # batch_size >= 1
                p, s, im0, frame = path[i], '%g: ' % i, im0s[i].copy(), dataset.count
            else:
                p, s, im0, frame = path, '', im0s, getattr(dataset, 'frame', 0)

            p = Path(p)  # to Path
            save_path = str(save_dir / p.name)  # img.jpg
            txt_path = str(save_dir / 'labels' / p.stem) + ('' if dataset.mode == 'image' else f'_{frame}')  # img.txt
            gn = torch.tensor(im0.shape)[[1, 0, 1, 0]]  # normalization gain whwh
            if len(det):
                # Rescale boxes from img_size to im0 size
                det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()

                # Print results
                for c in det[:, -1].unique():
                    n = (det[:, -1] == c).sum()  # detections per class
                    s += f"{n} {names[int(c)]}{'s' * (n > 1)}, "  # add to string
                    results_wrinkle.append(names[int(c)])  # 將出現的結果放入result_wrinkle

                # Write results
                for *xyxy, conf, cls in reversed(det):
                    if save_txt:  # Write to file
                        xywh = (xyxy2xywh(torch.tensor(xyxy).view(1, 4)) / gn).view(-1).tolist()  # normalized xywh
                        line = (cls, *xywh, conf) if opt.save_conf else (cls, *xywh)  # label format
                        with open(txt_path + '.txt', 'a') as f:
                            f.write(('%g ' * len(line)).rstrip() % line + '\n')

                    if save_img or view_img:  # Add bbox to image
                        label = f'{names[int(cls)]} {conf:.2f}'
                        plot_one_box(xyxy, im0, label=label, color=colors[int(cls)], line_thickness=1)

            # Print time (inference + NMS)
            # print(f'{s}Done. ({(1E3 * (t2 - t1)):.1f}ms) Inference, ({(1E3 * (t3 - t2)):.1f}ms) NMS')
            # {results_wrinkle}Done.
            time_process = f'({(1E3 * (t2 - t1)):.1f}ms) Inference, ({(1E3 * (t3 - t2)):.1f}ms) NMS'
            time_process += f' | FPS : {1 / (t3 - t1): .1f} '
            print(time_process)

            # Stream results
            if view_img:
                cv2.imshow(str(p), im0)
                cv2.waitKey(1)  # 1 millisecond

            # Save results (image with detections)
            if save_img:
                if dataset.mode == 'image':
                    cv2.imwrite(save_path, im0)
                    print(f" The image with the result is saved in: {save_path}")
                else:  # 'video' or 'stream'
                    if vid_path != save_path:  # new video
                        vid_path = save_path
                        if isinstance(vid_writer, cv2.VideoWriter):
                            vid_writer.release()  # release previous video writer
                        if vid_cap:  # video
                            fps = vid_cap.get(cv2.CAP_PROP_FPS)
                            w = int(vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            h = int(vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        else:  # stream
                            fps, w, h = 30, im0.shape[1], im0.shape[0]
                            save_path += '.mp4'
                        vid_writer = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
                    vid_writer.write(im0)

        count_1 += 1
        # if count_1 == 20:
        #     cv2.destroyAllWindows()
        #     break
    cv2.destroyAllWindows()

    if save_txt or save_img:
        s = f"\n{len(list(save_dir.glob('labels/*.txt')))} labels saved to {save_dir / 'labels'}" if save_txt else ''
        # print(f"Results saved to {save_dir}{s}")

    result_counter = Counter(results_wrinkle)  # 使用 Counter 統計結果出現次數
    unique_chars = set(result_counter)  # 找出出現的類別

    print(f'Done. ({time.time() - t0:.3f}s)')

    return unique_chars


app = Flask(__name__)


# 設置路由，將靜態文件提供給用戶訪問
@app.route('/')
def index():
    video_filename = result_url
    prod_des = prod_desc
    return render_template('/index.html', video_filename=video_filename, prod_des=prod_des)


# 取得api.json
@app.route('/api.json')
def get_api_json():
    return send_file('api.json')


# 路由來取得chatgpt的回應
@app.route('/get_openai_response', methods=['POST'])
def get_openai_response():
    user_input = request.json['user_input']
    # 使用 OpenAI Python 庫進行 API 請求
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system",
             "content": f"你是一個克蘭詩美容產品專員，負責招待客人，你剛剛推薦{product_result}這項產\
                品給{string_result}的客人了解，繼續解決客人的疑問，也可以推薦不同的產品，但必須是克蘭詩的產品，回答內容在50字以內"},
            {"role": "user", "content": user_input}
        ]
    )

    response = completion["choices"][0]["message"]["content"]
    print(len(response))
    return jsonify(response=response)


"""
API KEY 需自行上Azure上使用學校帳號申請
"""
azure_api_key = "XXX"
azure_region = "XXX"


# 執行語音識別
def transcribe_audio(speech_config):
    audio_config = speechsdk.AudioConfig(use_default_microphone=True)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    result = speech_recognizer.recognize_once_async().get()
    return result.text.strip()


# 異步路由來獲取語音識別結果
@app.route('/recognize_audio', methods=['POST'])
async def recognize_audio():
    # 建立 Azure 語音辨識的 SpeechConfig
    speech_config = speechsdk.SpeechConfig(subscription=azure_api_key, region=azure_region,
                                           speech_recognition_language='zh-TW')

    # 執行語音辨識
    result_text = transcribe_audio(speech_config)

    # 回傳辨識結果
    return jsonify(result_text=result_text)


if __name__ == "__main__":

    # # Age-gender-detection

    agd_parser = ArgumentParser(description='Using OpenCV to detect the age and gender of people')
    agd_parser.add_argument("-fprotp", help='input face proto file path', type=str,
                            default="AGE-Gender-Detection/opencv_face_detector.pbtxt")
    agd_parser.add_argument("-fmodel", help='input face model file path', type=str,
                            default="AGE-Gender-Detection/opencv_face_detector_uint8.pb")
    agd_parser.add_argument("-aprotp", help='input age proto file path', type=str,
                            default="AGE-Gender-Detection/age_deploy.prototxt")
    agd_parser.add_argument("-amodel", help='input age model file path', type=str,
                            default="AGE-Gender-Detection/age_net.caffemodel")
    agd_parser.add_argument("-gprotp", help='input gender proto file path', type=str,
                            default="AGE-Gender-Detection/gender_deploy.prototxt")
    agd_parser.add_argument("-gmodel", help='input gender model file path', type=str,
                            default="AGE-Gender-Detection/gender_net.caffemodel")
    agd_args = agd_parser.parse_known_args()

    faceProto = agd_args[0].fprotp
    faceModel = agd_args[0].fmodel

    ageProto = agd_args[0].aprotp
    ageModel = agd_args[0].amodel

    genderProto = agd_args[0].gprotp
    genderModel = agd_args[0].gmodel

    gender_age_result = run(faceProto, faceModel, ageProto, ageModel, genderProto, genderModel)
    # run(faceProto, faceModel, ageProto, ageModel, genderProto, genderModel)

    # yolov7 detect.py
    parser = ArgumentParser(description='Using YOLOv7 to detect the wrinkles and spots')
    parser.add_argument('--weights', nargs='+', type=str, default='best.pt', help='model.pt path(s)')
    parser.add_argument('--source', type=str, default='0', help='source')  # file/folder, 0 for webcam
    parser.add_argument('--img-size', type=int, default=640, help='inference size (pixels)')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='object confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='IOU threshold for NMS')
    parser.add_argument('--device', default='', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument('--view-img', action='store_true', help='display results')
    parser.add_argument('--save-txt', action='store_true', help='save results to *.txt')
    parser.add_argument('--save-conf', action='store_true', help='save confidences in --save-txt labels')
    parser.add_argument('--nosave', action='store_true', help='do not save images/videos')
    parser.add_argument('--classes', nargs='+', type=int, help='filter by class: --class 0, or --class 0 2 3')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--augment', action='store_true', help='augmented inference')
    parser.add_argument('--update', action='store_true', help='update all models')
    parser.add_argument('--project', default='runs/detect', help='save results to project/name')
    parser.add_argument('--name', default='exp', help='save results to project/name')
    parser.add_argument('--exist-ok', action='store_true', help='existing project/name ok, do not increment')
    parser.add_argument('--no-trace', action='store_false', help='don`t trace model')
    opt = parser.parse_args()
    # print(yolov7_opt)
    # check_requirements(exclude=('pycocotools', 'thop'))

    with torch.no_grad():
        if opt.update:  # update all models (to fix SourceChangeWarning)
            for opt.weights in ['yolov7.pt']:
                wrinkle_result = detect()
                strip_optimizer(opt.weights)
        else:
            wrinkle_result = detect()

    # 將所有辨識性別年齡以及有無皺紋黑斑的結果放到all_result
    all_result = []
    all_result.append(gender_age_result[0])
    all_result.append(gender_age_result[1])
    for a1 in wrinkle_result:
        # 輸出結果：['Female', '(15-20)', 'nasolabial folds', 'black_spot', 'crow-s feet', 'forehead wrinkles']
        all_result.append(a1)

    # all_result = ['Male', '(15-20)', 'black_spot']
    # 將all_result變成string，因為ChatGPT只能輸入str的格式(輸出結果：Female、(15-20)、nasolabial folds、black_spot、crow-s feet、forehead wrinkles)
    global string_result
    string_result = '、'.join(all_result)

    # 從csv檔中挑出適合的產品名稱與品牌以及產品的功效
    global product_result, prod_desc
    product_result, product_decribtion = choose_product(all_result)
    prod_desc = product_decribtion.replace(r'\r', '').replace(r'\n', '<br>')
    # product_decribtion=product_decribtion.replace("\n", "<br>")
    # prod_desc=product_decribtion
    print(product_result)
    print(prod_desc)
    print(string_result)

    openai.api_key = "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"

    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system",
             "content": "你是一個廣告文案師，請寫一段低於40字的中文廣告，將" + product_result + "的功效以及好處推薦給" + string_result + "年齡段的消費者"},
            {"role": "user", "content": "哪一種保養品適合我"}
        ]
    )

    word = completion["choices"][0]["message"]["content"]
    print(word)

    # print(len(word))
    # 取得D-ID API KEY
    with open('api.json', 'r') as file:
        data = json.load(file)

    value = data['key']
    base64_bytes = base64.b64encode(value.encode('ascii'))
    d_id_api = base64_bytes.decode('ascii')

    result_url = create_a_talk(word, d_id_api)
    print(result_url)

    webbrowser.open('http://127.0.0.1:3000')
    app.run(port=3000, threaded=True)