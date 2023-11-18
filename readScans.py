import re
import os
import easyocr
import pandas as pd
from pdf2image import convert_from_path  # requires poppler
from PIL import Image, ImageDraw, ImageFont
import argparse

reader = easyocr.Reader(["de"])

modelCodes = pd.read_csv("carcodes.csv")
# pat = r"( |^)HES[ ]?[0-9A-Z]{4}[ ]?[0-9A-Z]{10}($| )"
pat = r"( |^)\d{3}[.]\d{3}[.]\d{3}($| )"


def analyzeOcrOutput(bound, pageNo):
    # search for the fahrgestellnr, extract, map to Typengenehmigung
    tg = "UNKNOWN"
    id_num = "000.000.000"
    tg_loc = (0,)
    tg_owner_loc = (0,)

    for box in bound:
        # find_vin = re.search(pat, box[1])
        find_sn = re.search(pat, box[1])
        if find_sn is not None:
            id_num = find_sn.group(0).replace(" ", "")
            # id_num = find_vin.group(0).replace(" ", "")
            if id_num not in modelCodes["SN"].to_list():
                print(
                    f"WARNING: Could not map Stammnummer {id_num} to any TG on page {pageNo}"
                )
            else:
                tg = modelCodes.loc[modelCodes["SN"] == id_num, "TG"].values[0]

        elif re.search("Typengenehmigung( |$)", box[1]) is not None:
            tg_loc = box[0]  # (tl, tr, br, bl)

        elif re.search("Code du titulaire", box[1]) is not None:
            tg_owner_loc = box[0]  # (tl, tr, br, bl)

    return [id_num, tg, tg_loc, tg_owner_loc]


def findFontSize(ID, tg_width):
    fontsize = 20
    tl = 0
    while tl < tg_width * 1.5:
        font = ImageFont.truetype("arial.ttf", fontsize)
        tl = ID.textlength("TESTTEST", font=font)
        fontsize = int(fontsize * 1.05)

    return font


def fillForm(ID, tg, tg_loc, tg_owner_loc, tg_width, font, rgb=False):
    if rgb:
        black = (0, 0, 0)
    else:
        black = 0

    ID.text((tg_loc[1][0] + int(tg_width / 2), tg_loc[0][1]), tg, black, font=font)
    ID.text(
        (tg_owner_loc[1][0] + tg_width * 0.75, tg_owner_loc[0][1]),
        "8236",
        black,
        font=font,
    )


def readScans(
    filename="scans.pdf", start=1, output="out.pdf", verbose=True, debug=False
):
    if verbose and debug:
        print("==========\nDEBUG MODE", end="\n==========\n")

    # read in pdf
    if verbose:
        print(f"Reading {filename}...", flush=True, end="")
    pages = convert_from_path(filename, 800)  # second input is DPI
    if verbose:
        print("done!")
    no_of_pages = len(pages)

    if start > 1:
        if "failsafe.csv" in os.listdir():
            infos = pd.read_csv("failsafe.csv", index_col=0)
        else:
            raise ValueError("No 'failsafe.csv' available to do start>1.")
    else:
        infos = pd.DataFrame(columns=["page", "id", "tg", "tg_loc", "tg_owner_loc"])
        infos.page = range(1, no_of_pages + 1)
        infos.set_index("page", inplace=True)

    images = []
    empty_images = []
    font = None

    for i, page in enumerate(pages, 1):
        if verbose:
            print(f"Working on page {i}")
        # convert first to jpg
        if verbose:
            print("- Saving as jpg...", flush=True, end="")
        page.save(f"scan{i}.jpg")
        if verbose:
            print("done!")

        # read the image
        if i >= start:
            if verbose:
                print("- Performing OCR...", flush=True, end="")
            bound = reader.readtext(f"scan{i}.jpg")
            info = analyzeOcrOutput(bound, i)
            if verbose:
                print("done!")
            infos.loc[i] = info
        else:
            if verbose:
                print(f"Loading info for page {i} from failsafe.")

        _, tg, tg_loc, tg_owner_loc = infos.loc[i]

        if (info[1].lower() == "unknown") or (tg_loc[0] == 0) or (tg_owner_loc[0] == 0):
            # something went wrong, initiate failsafe
            infos.to_csv("failsafe.csv")
            raise ValueError(f"Issue with page {i}, cannot proceed.")

        tg_width = tg_loc[1][0] - tg_loc[0][0]

        if font is None:
            img = Image.open(f"scan{i}.jpg")
            ID = ImageDraw.Draw(img)
            # do this only the first time, the other pages should match
            font = findFontSize(ID, tg_width)
            imgSize = img.size

        txt_img = Image.new("1", imgSize, 1)
        ID_text = ImageDraw.Draw(txt_img)
        fillForm(ID_text, tg, tg_loc, tg_owner_loc, tg_width, font)
        empty_images.append(txt_img)

        if debug:
            img = Image.open(f"scan{i}.jpg")
            ID = ImageDraw.Draw(img)
            fillForm(ID, tg, tg_loc, tg_owner_loc, tg_width, font, rgb=True)
            img.show()
            images.append(img)

    if debug:
        images[0].save("out_debug.pdf", save_all=True, append_images=images[1:])
    else:
        # clean up
        for i in range(1, no_of_pages + 1):
            os.remove(f"scan{i}.jpg")

        if "failsafe.csv" in os.listdir():
            os.remove("failsafe.csv")

    empty_images[0].save("out.pdf", save_all=True, append_images=empty_images[1:])

    if verbose:
        print(f"Done. Output is stored in '{output}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Reads a bunch of forms and creates"
            "a pdf that can be printed that fills out the forms."
        )
    )

    parser.add_argument("-f", "--filename", default="scans.pdf")
    parser.add_argument("-s", "--start", default=1, type=int)
    parser.add_argument("-v", "--verbose", action="store_false")
    parser.add_argument("-d", "--debug", action="store_true")
    args = parser.parse_args()
    readScans(
        filename=args.filename, start=args.start, verbose=args.verbose, debug=args.debug
    )
