from bs4 import BeautifulSoup
import os, re

def extract_wiki_content(html_file, title):
    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    content = soup.find('div', {'class': 'mw-parser-output'})
    if not content:
        content = soup.find('div', {'id': 'mw-content-text'})
    if not content:
        content = soup
    for tag in content.find_all(['script', 'style', 'link']):
        tag.decompose()
    # Process tables into readable text
    for table in content.find_all('table'):
        rows = table.find_all('tr')
        if rows:
            table_text = []
            for row in rows:
                cells = row.find_all(['th', 'td'])
                cell_texts = [cell.get_text(separator=' ', strip=True) for cell in cells]
                if cell_texts:
                    table_text.append(' | '.join(cell_texts))
            if table_text:
                new_tag = soup.new_tag('p')
                new_tag.string = '\n'.join(table_text)
                table.replace_with(new_tag)
    text = content.get_text(separator='\n', strip=False)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return '=' * 60 + '\n  ' + title + '\n' + '=' * 60 + '\n\n' + text.strip()

pages = [
    ('Mythological_Ritual.html', 'MYTHOLOGICAL RITUAL (Diana Event)'),
    ('Spooky_Festival.html', 'SPOOKY FESTIVAL'),
    ("Jerry%27s_Workshop.html", "JERRY'S WORKSHOP / SEASON OF JERRY"),
    ('Dark_Auction.html', 'DARK AUCTION'),
    ('Traveling_Zoo.html', 'TRAVELING ZOO'),
    ('Mining_Fiesta.html', 'MINING FIESTA'),
    ('Fishing_Festival.html', 'FISHING FESTIVAL'),
    ('New_Year_Celebration.html', 'NEW YEAR CELEBRATION'),
    ("Jacob%27s_Farming_Contest.html", "JACOB'S FARMING CONTEST"),
    ('Election.html', 'MAYOR ELECTION SYSTEM'),
]

output = []
for fn, title in pages:
    fp = os.path.join('/tmp/wiki_scrape', fn)
    if os.path.exists(fp):
        try:
            r = extract_wiki_content(fp, title)
            output.append(r)
            print(f'OK: {title} ({len(r)} chars)')
        except Exception as e:
            print(f'ERR: {title}: {e}')

outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'events_knowledge.txt')
os.makedirs(os.path.dirname(outpath), exist_ok=True)
with open(outpath, 'w', encoding='utf-8') as f:
    f.write('\n\n\n'.join(output))
print(f'\nTotal: {sum(len(o) for o in output)} chars')
print(f'Written to: {outpath}')
