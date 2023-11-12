import easyocr
import pandas as pd
from pdf2image import convert_from_path # requires poppler
from PIL import Image, ImageDraw, ImageFont

reader = easyocr.Reader(["de"])

modelCodes = pd.read_csv("carcodes.csv")
# pat = r"( |^)HES[ ]?[0-9A-Z]{4}[ ]?[0-9A-Z]{10}($| )"
pat = r"( |^)\d{3}[.]\d{3}[.]\d{3}($| )"

scans = "examples.pdf"

# read in pdf
pages = convert_from_path(scans, 800) # second input is DPI
no_of_pages = len(pages)

infos = pd.DataFrame(columns = ["page", "id", "tg", "tg_loc", "tg_owner_loc"]) 
infos.page = range(1, no_of_pages+1)

images = []
empty_images = []

for i, page in enumerate(pages):
    print(f"Working on page {i+1}")
    #convert first to jpg
    page.save("scan.jpg")

    # read the image
    bound = reader.readtext("scan.jpg")

    # search for the fahrgestellnr, extract, map to Typengenehmigung
    for box in bound:
        # find_vin = re.search(pat, box[1])
        find_sn = re.search(pat, box[1])
        if find_sn is not None:
            id_num = find_sn.group(0).replace(" ", "")
            # id_num = find_vin.group(0).replace(" ", "")
            if id_num not in modelCodes["SN"].to_list():
                print(f"WARNING: Could not map Stammnummer {id_num} to any TG on page {i+1}")
                tg = "UNKNOWN"
            else:
                tg = modelCodes.loc[modelCodes["SN"] == id_num, "TG"].values[0]
                infos.loc[i, "tg"] = tg
            infos.loc[i, "id"] = id_num
            
        find_tg = re.search("Typengenehmigung( |$)", box[1])
        if find_tg is not None:
            tg_loc = box[0] # (tl, tr, br, bl)
            infos.loc[i, "tg_loc"] = ((tg_loc), )

        find_tg_owner = re.search("Code du titulaire", box[1])
        if find_tg_owner is not None:
            tg_owner_loc = box[0] # (tl, tr, br, bl)
            infos.loc[i, "tg_owner_loc"] = ((tg_owner_loc), )

    img = Image.open("scan.jpg")
    tg_width = tg_loc[1][0] - tg_loc[0][0]
    fontsize = 50
    ID = ImageDraw.Draw(img)
    tl = 0
    while tl < tg_width*1.5:
        font = ImageFont.truetype("arial.ttf", fontsize)
        tl = ID.textlength("TESTTEST", font = font)
        fontsize = int(fontsize*1.05)
    
    ID.text((tg_loc[1][0]+int(tg_width/2), tg_loc[0][1]), tg, (0, 0, 0), font=font)
    ID.text((tg_owner_loc[1][0]+tg_width*0.75, tg_owner_loc[0][1]), "8236", (0, 0, 0), font=font)

    images.append(img)
    # img.show()

    txt_img = Image.new("1", img.size, 1)
    ID_text = ImageDraw.Draw(txt_img)
    ID_text.text((tg_loc[1][0]+int(tg_width/2), tg_loc[0][1]), tg, 0, font=font)
    ID_text.text((tg_owner_loc[1][0]+tg_width, tg_owner_loc[0][1]), "8236", 0, font=font)
    # txt_img.show()
    empty_images.append(txt_img)

images[0].save("out_debug.pdf", save_all = True, append_images = images[1:])
empty_images[0].save("out.pdf", save_all = True, append_images = empty_images[1:])
    

