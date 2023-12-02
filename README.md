# MyBeautyAI

## Environment

> Tip: Create a conda environment and run below command

- `pip install -r requirements.txt`

## File Download

>  Move the traced_model.pt file to MyBeautyAI folder

- url:[traced_model.pt file](https://drive.google.com/file/d/1ho1tNiyQL7jx2DaxpsmQ-mTYnercyRQJ/view?usp=sharing)

## Modify Code

1. You need to have own **Azure API KEY and Build Azure Speech Service**, then modify corresponding code in connect.py
2. When you run the code and face the **can't have D-ID ID** problem, you need to change the API KEY. You can get it from **D-ID accounts.xlsx** file and modify api.json.

## Run Code in Terminal

> Tip: You must have to give the correct **connect.py path**

1. `cd {folder_path} `
2. `python connect.py`

## Architecture Diagram

![architecture](image/README/architecture.png)

## Responsible Parts

> If you have any questions, please contact the corresponding person first.

- Front-end (index.html): 趙家緯
- Dataset (CareProduct_clarins.csv & embedding-clarins.docx): 江家恩
- Front-end (index.js) / Back-end (connect.py architecture and flask): 蔡芊葳
- Back-end (All except front-end): 黃淳庭
