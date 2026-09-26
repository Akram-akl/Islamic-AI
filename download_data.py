import urllib.request
import os

def download_data():
    data_dir = r"c:\Users\akram\OneDrive\Desktop\appsakramakl\Islamic-AI\data"
    os.makedirs(data_dir, exist_ok=True)

    print("جاري تحميل القرآن الكريم (نسخة موثوقة JSON)...")
    quran_url = "https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1/editions/ara-quran-la.json"
    try:
        urllib.request.urlretrieve(quran_url, os.path.join(data_dir, "quran.json"))
        print("تم تحميل القرآن.")
    except Exception as e:
        print(f"خطأ في تحميل القرآن: {e}")

    print("جاري تحميل صحيح البخاري...")
    bukhari_url = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/ara-bukhari.json"
    try:
        urllib.request.urlretrieve(bukhari_url, os.path.join(data_dir, "bukhari.json"))
        print("تم تحميل البخاري.")
    except Exception as e:
        print(f"خطأ في تحميل البخاري: {e}")

    print("انتهت عملية التحميل!")

if __name__ == "__main__":
    download_data()
