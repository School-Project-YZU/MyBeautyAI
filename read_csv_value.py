import pandas as pd

def choose_product(s):
    # 讀取CSV文件
    df = pd.read_csv('CareProduct.csv', encoding='UTF-8-sig')

    # 隨機的條件列表
    # s = ['Male', '(15-20)', 'black_spot']

    # 構建包含皺紋和黑斑的條件選擇
    condition = (df['性別'] == s[0]) & (df['年齡'] == s[1])

    has_wrinkles = False
    has_black_spot = False

    for i in range(2, len(s)):
        if s[i] == 'nasolabial folds' or s[i] == 'forehead wrinkles' or s[i] == "crow's feet":
            has_wrinkles = True
        elif s[i] == 'black_spot':
            has_black_spot = True

    # 檢查是否有皺紋和黑斑的條件
    if has_wrinkles == True and has_black_spot == True:
        condition = condition & (df['臉部情況'].str.contains('有皺紋有黑斑'))
    elif has_wrinkles == False and has_black_spot == True:
        condition = condition & (df['臉部情況'].str.contains('無皺紋有黑斑'))
    elif has_wrinkles == True and has_black_spot == False:
        condition = condition & (df['臉部情況'].str.contains('有皺紋無黑斑'))
    else:
        condition = condition & (df['臉部情況'].str.contains('無皺紋無黑斑'))

    # 條件選擇：獲取符合條件的行
    result = df[condition][['品牌', '產品名稱']]

    # 輸出結果
    # print(result.to_string(index=False, header=False))
    return result.to_string(index=False, header=False)