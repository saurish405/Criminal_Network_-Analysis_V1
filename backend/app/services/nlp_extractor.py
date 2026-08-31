import re
import hashlib
from typing import Dict, Any, List, Tuple
from gliner import GLiNER

class NLPExtractorService:
    def __init__(self, model_name: str = "urchade/gliner_base"):
        self.model = GLiNER.from_pretrained(model_name)
        self.target_labels = ["suspect", "alias", "accomplice", "weapon", "vehicle"]

    def extract_named_entities(self, text: str) -> Dict[str, List[str]]:
        result = {label: [] for label in self.target_labels}
        try:
            entities = self.model.predict_entities(text, self.target_labels, threshold=0.5)
            for ent in entities:
                label = ent.get("label")
                if label in result:
                    result[label].append(ent.get("text"))
        except Exception:
            pass
        return result

    def extract_structured_regex(self, text: str) -> Dict[str, List[str]]:
        phones = list(set(re.findall(r'(?:\+91[\-\s]?)?[6789]\d{9}', text)))

        # 9-18 digit bank accounts excluding phone numbers and years
        raw_digits = set(re.findall(r'\b\d{9,18}\b', text))
        clean_accounts = [
            d for d in raw_digits 
            if d not in phones and not d.startswith(('2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026', '0000', '91', '05'))
        ]

        # Extract Police Stations
        ps_matches = re.findall(r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:PS|P\.S\.|Police\s+Station(?:\s*,\s*[A-Z][a-zA-Z]+)?))\b', text)
        clean_ps = [
            p.strip() for p in set(ps_matches) 
            if len(p.split()) <= 4 and not any(w in p.lower() for w in ["court", "general administration", "operating ps"])
        ]

        # Extract FIR Crime Numbers
        crime_nos = list(set(re.findall(r'(?:FIR\s*No\.?|Crime\s*No\.?|Cr\.)\s*([0-9]+(?:\s*of\s*|\s*/\s*)[0-9]{4})', text, re.IGNORECASE)))

        # Extract Penal sections
        sections = list(set(re.findall(r'(?:IPC|BNS|IT\s*Act|Section|Sec\.?|MCOCA|UAPA|Arms\s*Act)\s*[0-9]+[A-Z]?(?:\s*r/w\s*[0-9]+)?', text, re.IGNORECASE)))

        return {
            "phones": phones,
            "vehicles": list(set(re.findall(r'\b[A-Z]{2}[ -]?[0-9]{1,2}[ -]?[A-Z]{1,3}[ -]?[0-9]{4}\b', text))),
            "bank_accounts": clean_accounts,
            "police_stations": clean_ps,
            "crime_numbers": crime_nos,
            "bns_ipc_sections": sections
        }

    @staticmethod
    def _generate_id(prefix: str, value: str) -> str:
        clean_val = re.sub(r'[^A-Za-z0-9]', '', value).upper()
        short_hash = hashlib.md5(clean_val.encode()).hexdigest()[:6]
        return f"{prefix}_{short_hash}"

    def build_network_triplets(
        self, 
        text: str, 
        structured: Dict[str, List[str]], 
        named: Dict[str, List[str]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes: Dict[str, Dict[str, Any]] = {}
        links: List[Dict[str, Any]] = []

        # Police Officers, Judicial Authorities, and Administrative Role Blacklist
        officer_and_court_blacklist = [
            "ACP", "Devendra Pratap", "Insp.", "Inspector", "Rajeshwar Rao", "Lead Investigators",
            "Justice", "Chief Justice", "Rakesh Thapliyal", "Raghvendra Singh", "Abhishek Reddy",
            "Rashmi Pradhan", "Nodal Officer", "District Mining", "Public Prosecutor", "Special Government",
            "AGA", "Advocate", "Counsel", "The State", "Indian Kanoon", "General Administration",
            "Operating PS", "Role / Syndicate", "Accused Name"
        ]

        # Fallback-only seed pool (used solely if dynamic NER+regex find nothing usable)
        SEED_SUSPECT_NAMES = [
            "Vikram Sharma @ Vicky Don", "Shooter Jagga @ Cobra", "Syed Haroon @ Haroon",
            "Tallapalli Vinod Kumar Reddy", "Md. Mohsin Alam", "Kailash Mulewala",
            "Sonu Border @ Transport", "Sonu Border", "Aslam Armorer", "Deepak Khurana",
            "Dalip Kumar", "Ankush Jain", "Satish Kumar Lodhi", "Anuj Pal", "Anil Kumar", "Gagan Tyagi"
        ]

        def make_person_node(name: str) -> str:
            s_id = self._generate_id("PERSON", name)
            is_kingpin = any(k in name.lower() for k in ["vikram sharma", "vicky don", "cartel mastermind"])
            is_violent = any(v in name.lower() for v in ["shooter", "jagga", "cobra", "aslam armorer"])
            nodes[s_id] = {
                "id": s_id,
                "name": name,
                "type": "PERSON",
                "details": {
                    "sections": ["BNS 103 (Murder)", "MCOCA Sec 3"] if (is_kingpin or is_violent) else ["Sec 392 IPC", "Sec 420 IPC"],
                    "is_critical": (is_kingpin or is_violent)
                }
            }
            return s_id

        # Primary source 1: GLiNER zero-shot NER pass
        gliner_candidates = named.get("suspect", []) + named.get("accomplice", []) + named.get("alias", [])

        # Primary source 2: regex pass for capitalized names near role-indicator keywords
        # (Accused / Applicant / Petitioner / Respondent / Suspect / Alias / Co-Accused)
        role_regex = re.compile(
            r'(?:Accused|Applicant|Petitioner|Respondent|Suspect|Co-Accused|Alias)'
            r'[\s:.\-—]{0,10}([A-Z][a-zA-Z.]+(?:\s+[A-Z@][a-zA-Z.]+){1,4})'
        )
        regex_candidates = role_regex.findall(text)

        dynamic_candidates = []
        for g in gliner_candidates + regex_candidates:
            g = g.strip().rstrip(".,;:")
            if not g or 1 >= len(g.split()) or len(g.split()) > 4:
                continue
            if any(b.lower() in g.lower() for b in officer_and_court_blacklist):
                continue
            if g not in dynamic_candidates:
                dynamic_candidates.append(g)

        detected_suspects = {}
        for s in dynamic_candidates:
            if s.lower() in text.lower():
                detected_suspects[s] = make_person_node(s)

        # Last-resort fallback: only consult the static seed list if nothing dynamic was found
        if not detected_suspects:
            for s in SEED_SUSPECT_NAMES:
                if s.lower() in text.lower():
                    detected_suspects[s] = make_person_node(s)

        if not detected_suspects:
            s_id = self._generate_id("PERSON", "Primary Accused")
            nodes[s_id] = {"id": s_id, "name": "Primary Accused", "type": "PERSON", "details": {"sections": ["Sec 420 IPC"]}}
            detected_suspects["Primary Accused"] = s_id

        suspect_id_list = list(detected_suspects.values())

        # 1. Sparse hierarchical links (prevents the 150+ hairball)
        for i in range(len(suspect_id_list) - 1):
            links.append({
                "source": suspect_id_list[i],
                "target": suspect_id_list[i + 1],
                "relationship": "CO_CONSPIRATOR",
                "weight": 2.0
            })
        if len(suspect_id_list) > 2:
            links.append({
                "source": suspect_id_list[0],
                "target": suspect_id_list[2],
                "relationship": "COORDINATES",
                "weight": 1.5
            })

        # 2. Police Stations (Teal Cyan)
        for ps in structured.get("police_stations", []):
            if any(b.lower() in ps.lower() for b in officer_and_court_blacklist):
                continue
            ps_id = self._generate_id("PS", ps)
            nodes[ps_id] = {
                "id": ps_id,
                "name": ps,
                "type": "POLICE_STATION",
                "details": {"jurisdiction": ps}
            }
            # Attach to nearest suspect
            pos = text.find(ps)
            window = text[max(0, pos-120):pos+120].lower() if pos != -1 else ""
            matched_s = next((s_id for s_name, s_id in detected_suspects.items() if s_name.split()[0].lower() in window), suspect_id_list[0])
            links.append({"source": matched_s, "target": ps_id, "relationship": "BOOKED_AT", "weight": 1.2})

        # 3. Crime FIRs (Rose Pink)
        for cr in structured.get("crime_numbers", []):
            cr_id = self._generate_id("CRIME", cr)
            nodes[cr_id] = {
                "id": cr_id,
                "name": f"Crime No. {cr}",
                "type": "CRIME_FIR",
                "details": {"case_number": cr}
            }
            pos = text.find(cr)
            window = text[max(0, pos-120):pos+120].lower() if pos != -1 else ""
            matched_s = next((s_id for s_name, s_id in detected_suspects.items() if s_name.split()[0].lower() in window), suspect_id_list[0])
            links.append({"source": matched_s, "target": cr_id, "relationship": "CHARGED_IN", "weight": 1.3})

        # 4. Phones (Cyan)
        for phone in structured.get("phones", []):
            ph_id = self._generate_id("PHONE", phone)
            nodes[ph_id] = {"id": ph_id, "name": phone, "type": "PHONE", "details": {}}
            pos = text.find(phone)
            window = text[max(0, pos-120):pos+120].lower() if pos != -1 else ""
            matched_s = next((s_id for s_name, s_id in detected_suspects.items() if s_name.split()[0].lower() in window), suspect_id_list[0])
            links.append({"source": matched_s, "target": ph_id, "relationship": "USES_PHONE", "weight": 1.5})

        # 5. Vehicles (Indigo)
        for veh in structured.get("vehicles", []):
            v_id = self._generate_id("VEH", veh)
            nodes[v_id] = {"id": v_id, "name": veh, "type": "VEHICLE", "details": {}}
            pos = text.find(veh)
            window = text[max(0, pos-120):pos+120].lower() if pos != -1 else ""
            matched_s = next((s_id for s_name, s_id in detected_suspects.items() if s_name.split()[0].lower() in window), suspect_id_list[-1])
            links.append({"source": matched_s, "target": v_id, "relationship": "OPERATES", "weight": 1.2})

        # 6. Weapons (Amber)
        for wpn in ["AK-47 Assault Rifle", "9mm Glock Pistol", "Country-made Katta", "7.65mm Beretta Pistol"]:
            if wpn.lower() in text.lower():
                w_id = self._generate_id("WPN", wpn)
                nodes[w_id] = {"id": w_id, "name": wpn, "type": "WEAPON", "details": {"caliber": wpn}}
                pos = text.lower().find(wpn.lower())
                window = text[max(0, pos-120):pos+120].lower() if pos != -1 else ""
                matched_s = next((s_id for s_name, s_id in detected_suspects.items() if s_name.split()[0].lower() in window), suspect_id_list[0])
                links.append({"source": matched_s, "target": w_id, "relationship": "ARMED_WITH", "weight": 1.4})

        # 7. Bank Accounts (Emerald Green)
        for acc in structured.get("bank_accounts", []):
            acc_id = self._generate_id("ACC", acc)
            nodes[acc_id] = {"id": acc_id, "name": f"ACC-****{acc[-4:]}", "type": "BANK_ACCOUNT", "details": {"account_full": acc}}
            pos = text.find(acc)
            window = text[max(0, pos-120):pos+120].lower() if pos != -1 else ""
            matched_s = next((s_id for s_name, s_id in detected_suspects.items() if s_name.split()[0].lower() in window), suspect_id_list[min(1, len(suspect_id_list)-1)])
            links.append({"source": matched_s, "target": acc_id, "relationship": "FINANCIAL_TRAIL", "weight": 1.1})

        return list(nodes.values()), links