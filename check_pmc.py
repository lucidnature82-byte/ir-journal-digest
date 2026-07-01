"""PMC Open Access 논문 + figure 가용성 확인 (XML 버전)"""
import json
import requests
import time
import xml.etree.ElementTree as ET

with open('data/2026-05.json', encoding='utf-8') as f:
    articles = json.load(f)

with_abstract = [a for a in articles if a.get('abstract')]
print(f"총 abstract 있는 논문: {len(with_abstract)}편")
print(f"PMC 등록 여부 확인 중...\n")


def check_pmc_batch(pmids):
    """PMID 배치를 PMC ID로 변환 (XML 응답)"""
    ids_str = ','.join(pmids)
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
    params = {
        'dbfrom': 'pubmed',
        'db': 'pmc',
        'id': ids_str,
        'retmode': 'xml'   # JSON 대신 XML
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_pmc_xml(xml_text):
    """XML 응답에서 PMID → PMC ID 매핑 추출"""
    mapping = {}
    try:
        root = ET.fromstring(xml_text)
        for linkset in root.findall('.//LinkSet'):
            # 입력 PMID
            id_elem = linkset.find('./IdList/Id')
            if id_elem is None:
                continue
            pmid = id_elem.text
            
            # PMC ID
            for linksetdb in linkset.findall('./LinkSetDb'):
                dbto = linksetdb.find('DbTo')
                if dbto is not None and dbto.text == 'pmc':
                    link = linksetdb.find('./Link/Id')
                    if link is not None:
                        mapping[pmid] = f"PMC{link.text}"
                    break
    except ET.ParseError as e:
        print(f"  XML 파싱 에러: {e}")
    return mapping


# 전체 PMID
all_pmids = [a['pmid'] for a in with_abstract]
pmc_mapping = {}

# 50편씩 배치 처리
for i in range(0, len(all_pmids), 50):
    batch = all_pmids[i:i+50]
    print(f"  배치 {i//50 + 1}: {len(batch)}편 확인 중...")
    try:
        xml_text = check_pmc_batch(batch)
        batch_mapping = parse_pmc_xml(xml_text)
        pmc_mapping.update(batch_mapping)
    except Exception as e:
        print(f"  에러 (배치 {i//50 + 1}): {e}")
    time.sleep(0.5)

# 결과 요약
print("\n" + "=" * 60)
print(f"전체: {len(all_pmids)}편")
print(f"PMC 공개: {len(pmc_mapping)}편 ({len(pmc_mapping)/len(all_pmids)*100:.0f}%)")
print(f"비공개:   {len(all_pmids) - len(pmc_mapping)}편")
print("=" * 60)

# PMC 공개 논문 샘플
if pmc_mapping:
    print("\nPMC 공개 논문 (최대 10편 샘플):")
    sample_count = 0
    for a in with_abstract:
        if a['pmid'] in pmc_mapping:
            pmcid = pmc_mapping[a['pmid']]
            title = (a.get('title') or '')[:50]
            journal = a.get('journal', '?')
            print(f"  [{journal}] PMID {a['pmid']} → {pmcid}")
            print(f"      {title}...")
            sample_count += 1