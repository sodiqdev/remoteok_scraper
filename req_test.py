import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/115.0 Safari/537.36"
}

job_id = 1093848
url = f"https://remoteok.com/remote-jobs/{job_id}"

resp = requests.get(url, allow_redirects=True, headers=HEADERS, timeout=30)
print("Final URL:", resp.url)
print("Status:", resp.status_code)

if resp.status_code == 200:
    soup = BeautifulSoup(resp.text, "html.parser")

    title = soup.find("title").text.strip()
    print("TITLE:", title)

    desc_tag = soup.find("meta", {"name": "description"})
    description = desc_tag["content"].strip() if desc_tag else ""
    print("DESCRIPTION:", description[:200])

    company_tag = soup.find("h3", {"itemprop": "name"})
    company = company_tag.text.strip() if company_tag else ""
    print("COMPANY:", company)

    location_tag = soup.find("div", {"class": "location"})
    location = location_tag.text.strip() if location_tag else ""
    print("LOCATION:", location)

    logo_tag = soup.find("img", {"itemprop": "image"})
    company_logo = logo_tag["src"] if logo_tag else ""
    print("LOGO:", company_logo)

    apply_url_tag = soup.find("a", {"class": "action-apply"})
    apply_url = apply_url_tag["href"] if apply_url_tag else ""
    print("APPLY_URL:", apply_url)

    with open('job.html', 'wb') as f:
        f.write(resp.content)

else:
    print("❌ Error fetching job")
