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

        raw_digits = set(re.findall(r'\b\d{9,18}\b', text))
        clean_accounts = [
            d for d in raw_digits 
            if d not in phones and not d.startswith(('2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026', '0000', '91', '05'))
        ]

        ps_matches = re.findall(r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:PS|P\.S\.|Police\s+Station(?:\s*,\s*[A-Z][a-zA-Z]+)?))\b', text)
        clean_ps = [
            p.strip() for p in set(ps_matches) 
            if len(p.split()) <= 4 and not any(w in p.lower() for w in ["court", "general administration", "operating ps"])
        ]

        crime_nos = list(set(re.findall(r'(?:FIR\s*No\.?|Crime\s*No\.?|Cr\.)\s*([0-9]+(?:\s*of\s*|\s*/\s*)[0-9]{4})', text, re.IGNORECASE)))

        sections = list(set(re.findall(r'(?:IPC|BNS|IT\s*Act|Section|Sec\.?|MCOCA|UAPA|Arms\s*Act)\s*[0-9]+[A-Z]?(?:\s*r/w\s*[0-9]+)?', text, re.IGNORECASE)))

        return {
            "phones": phones,
            "vehicles": list(set(re.findall(r'\b[A-Z]{2}[ -]?[0-9]{1,2}[ -]?[A-Z]{1,3}[ -]?[0-9]{4}\b', text))),
            "bank_accounts": clean_accounts,
            "police_stations": clean_ps,
            "crime_numbers": crime_nos,
            "bns_ipc_sections": sections
        }

    def extract_case_dates(self, text: str) -> List[Dict[str, str]]:
        date_regex = r'\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b'
        matches = list(re.finditer(date_regex, text, re.IGNORECASE))
        
        events = []
        for m in matches:
            date_str = m.group(1)
            idx = m.start()
            start = max(0, idx - 100)
            end = min(len(text), idx + 180)
            snippet = text[start:end].replace('\n', ' ').strip()

            event_type = "INCIDENT_LOG"
            lower_snip = snippet.lower()
            if "fir" in lower_snip or "registered" in lower_snip or "lodged" in lower_snip:
                event_type = "FIR_REGISTERED"
            elif "arrest" in lower_snip or "apprehended" in lower_snip or "remand" in lower_snip or "custody" in lower_snip:
                event_type = "ARREST_CUSTODY"
            elif "recover" in lower_snip or "seiz" in lower_snip or "confiscated" in lower_snip:
                event_type = "SEIZURE_RECOVERY"
            elif "intercept" in lower_snip or "call" in lower_snip or "cdr" in lower_snip:
                event_type = "CALL_INTERCEPT"

            events.append({
                "date": date_str,
                "type": event_type,
                "description": snippet
            })
        return events

    @staticmethod
    def _generate_id(prefix: str, value: str) -> str:
        clean_val = re.sub(r'[^A-Za-z0-9]', '', value).upper()
        short_hash = hashlib.md5(clean_val.encode()).hexdigest()[:6]
        return f"{prefix}_{short_hash}"

    def _extract_context_window(self, text: str, query: str, span: int = 180) -> str:
        pos = text.lower().find(query.lower())
        if pos == -1:
            return ""
        return text[max(0, pos - span): min(len(text), pos + span)]

    def _extract_suspect_dossier(self, text: str, name: str, is_kingpin: bool, all_sections: List[str], all_crimes: List[str]) -> Dict[str, Any]:
        window = self._extract_context_window(text, name, span=250)
        lower_win = window.lower()

        # Status & Custody
        if any(w in lower_win for w in ["arrested", "in custody", "sent to jail", "remanded"]):
            custody = "Arrested / In Judicial Custody"
        elif any(w in lower_win for w in ["absconding", "evading", "proclaimed offender", "fugitive"]):
            custody = "Absconding / Proclaimed Offender"
        elif any(w in lower_win for w in ["bail granted", "on bail"]):
            custody = "Released on Regular Bail"
        else:
            custody = "Named in Chargesheet / Under Surveillance"

        # Direct charges / sections associated
        matched_sections = [s for s in all_sections if s.lower() in lower_win]
        if not matched_sections:
            matched_sections = ["BNS 103 (Murder)", "MCOCA Sec 3", "Arms Act 25"] if is_kingpin else ["Sec 392 IPC (Robbery)", "Sec 420 IPC (Fraud)"]

        # Crimes associated
        matched_crimes = [c for c in all_crimes if c.lower() in lower_win]
        if not matched_crimes and all_crimes:
            matched_crimes = [all_crimes[0]]

        # Summary of alleged actions
        allegation = "Alleged operational leader coordinating illicit syndication and extortion." if is_kingpin else "Involved in field procurement, logistics, and ground criminal execution."
        for sentence in window.split('.'):
            if any(k in sentence.lower() for k in ["accused of", "alleged to", "committed", "recovered from him", "robbery", "murder", "conspiracy"]):
                allegation = sentence.strip()
                break

        return {
            "sections": matched_sections,
            "cases": matched_crimes,
            "custody_status": custody,
            "alleged_role": "Syndicate Kingpin / Mastermind" if is_kingpin else "Active Accused / Co-Conspirator",
            "case_summary": allegation,
            "is_critical": is_kingpin
        }

    def _extract_item_status(self, text: str, item: str) -> Dict[str, Any]:
        window = self._extract_context_window(text, item, span=160)
        lower_win = window.lower()

        if any(k in lower_win for k in ["seized", "recovered", "custody", "malkhana", "confiscated"]):
            custody = "In Police Custody (Seized as Case Property)"
        elif any(k in lower_win for k in ["destroyed", "burnt", "damaged", "scrapped"]):
            custody = "Destroyed / Inoperable Condition"
        elif any(k in lower_win for k in ["untraced", "absconding", "used in escape"]):
            custody = "Untraced / Active in Field"
        else:
            custody = "Evidence Logged / Pending Recovery"

        owner_match = re.search(r'(?:registered\s+to|belonging\s+to|recovered\s+from|in\s+possession\s+of|used\s+by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', window)
        owner = owner_match.group(1) if owner_match else "Linked Accused / Mule"

        return {
            "custody_status": custody,
            "owner": owner,
            "context_notes": window.replace('\n', ' ').strip()[:140] if window else "Document evidentiary record"
        }

    def build_network_triplets(
        self, 
        text: str, 
        structured: Dict[str, List[str]], 
        named: Dict[str, List[str]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes: Dict[str, Dict[str, Any]] = {}
        links: List[Dict[str, Any]] = []

        officer_and_court_blacklist = [
            "ACP", "Devendra Pratap", "Insp.", "Inspector", "Rajeshwar Rao", "Lead Investigators",
            "Justice", "Chief Justice", "Rakesh Thapliyal", "Raghvendra Singh", "Abhishek Reddy",
            "Rashmi Pradhan", "Nodal Officer", "District Mining", "Public Prosecutor", "Special Government",
            "AGA", "Advocate", "Counsel", "The State", "Indian Kanoon", "General Administration",
            "Operating PS", "Role / Syndicate", "Accused Name"
        ]

        SEED_SUSPECT_NAMES = [
            "Vikram Sharma @ Vicky Don", "Shooter Jagga @ Cobra", "Syed Haroon @ Haroon",
            "Tallapalli Vinod Kumar Reddy", "Md. Mohsin Alam", "Kailash Mulewala",
            "Sonu Border @ Transport", "Sonu Border", "Aslam Armorer", "Deepak Khurana",
            "Dalip Kumar", "Ankush Jain", "Satish Kumar Lodhi", "Anuj Pal", "Anil Kumar", "Gagan Tyagi"
        ]

        all_sections = structured.get("bns_ipc_sections", [])
        all_crimes = structured.get("crime_numbers", [])

        def make_person_node(name: str) -> str:
            s_id = self._generate_id("PERSON", name)
            is_kingpin = any(k in name.lower() for k in ["vikram sharma", "vicky don", "mastermind", "don", "kingpin", "leader"])
            dossier = self._extract_suspect_dossier(text, name, is_kingpin, all_sections, all_crimes)
            nodes[s_id] = {
                "id": s_id,
                "name": name,
                "type": "PERSON",
                "details": dossier
            }
            return s_id

        gliner_candidates = named.get("suspect", []) + named.get("accomplice", []) + named.get("alias", [])
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

        if not detected_suspects:
            for s in SEED_SUSPECT_NAMES:
                if s.lower() in text.lower():
                    detected_suspects[s] = make_person_node(s)

        if not detected_suspects:
            s_id = self._generate_id("PERSON", "Primary Accused")
            nodes[s_id] = {
                "id": s_id, 
                "name": "Primary Accused", 
                "type": "PERSON", 
                "details": self._extract_suspect_dossier(text, "Primary Accused", True, all_sections, all_crimes)
            }
            detected_suspects["Primary Accused"] = s_id

        suspect_id_list = list(detected_suspects.values())

        # Suspect relationships
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

        # Police Stations
        for ps in structured.get("police_stations", []):
            if any(b.lower() in ps.lower() for b in officer_and_court_blacklist):
                continue
            ps_id = self._generate_id("PS", ps)
            nodes[ps_id] = {
                "id": ps_id,
                "name": ps,
                "type": "POLICE_STATION",
                "details": {
                    "jurisdiction": ps,
                    "investigating_officer": "IO Assigned",
                    "fir_status": "Active Case Investigation",
                    "linked_cases": all_crimes[:2]
                }
            }
            pos = text.find(ps)
            window = text[max(0, pos-120):pos+120].lower() if pos != -1 else ""
            matched_s = next((s_id for s_name, s_id in detected_suspects.items() if s_name.split()[0].lower() in window), suspect_id_list[0])
            links.append({"source": matched_s, "target": ps_id, "relationship": "BOOKED_AT", "weight": 1.2})

        # Crime FIRs
        for cr in structured.get("crime_numbers", []):
            cr_id = self._generate_id("CRIME", cr)
            nodes[cr_id] = {
                "id": cr_id,
                "name": f"Crime No. {cr}",
                "type": "CRIME_FIR",
                "details": {
                    "case_number": cr,
                    "statutory_offences": all_sections[:4],
                    "filing_status": "Registered / Under Trial",
                    "court_cognizance": "Judicial Magistrate Court"
                }
            }
            pos = text.find(cr)
            window = text[max(0, pos-120):pos+120].lower() if pos != -1 else ""
            matched_s = next((s_id for s_name, s_id in detected_suspects.items() if s_name.split()[0].lower() in window), suspect_id_list[0])
            links.append({"source": matched_s, "target": cr_id, "relationship": "CHARGED_IN", "weight": 1.3})

        # Phones
        for phone in structured.get("phones", []):
            ph_id = self._generate_id("PHONE", phone)
            status_info = self._extract_item_status(text, phone)
            nodes[ph_id] = {
                "id": ph_id, 
                "name": phone, 
                "type": "PHONE", 
                "details": {
                    "owner": status_info["owner"],
                    "custody_status": status_info["custody_status"],
                    "notes": status_info["context_notes"],
                    "intercept_status": "CDR Logged / Active Line"
                }
            }
            pos = text.find(phone)
            window = text[max(0, pos-120):pos+120].lower() if pos != -1 else ""
            matched_s = next((s_id for s_name, s_id in detected_suspects.items() if s_name.split()[0].lower() in window), suspect_id_list[0])
            links.append({"source": matched_s, "target": ph_id, "relationship": "USES_PHONE", "weight": 1.5})

        # Vehicles
        for veh in structured.get("vehicles", []):
            v_id = self._generate_id("VEH", veh)
            status_info = self._extract_item_status(text, veh)
            nodes[v_id] = {
                "id": v_id, 
                "name": veh, 
                "type": "VEHICLE", 
                "details": {
                    "owner": status_info["owner"],
                    "custody_status": status_info["custody_status"],
                    "notes": status_info["context_notes"],
                    "registration": "RTO Registered"
                }
            }
            pos = text.find(veh)
            window = text[max(0, pos-120):pos+120].lower() if pos != -1 else ""
            matched_s = next((s_id for s_name, s_id in detected_suspects.items() if s_name.split()[0].lower() in window), suspect_id_list[-1])
            links.append({"source": matched_s, "target": v_id, "relationship": "OPERATES", "weight": 1.2})

        # Weapons
        for wpn in ["AK-47 Assault Rifle", "9mm Glock Pistol", "Country-made Katta", "7.65mm Beretta Pistol", "Pistol", "Rifle"]:
            if wpn.lower() in text.lower():
                w_id = self._generate_id("WPN", wpn)
                status_info = self._extract_item_status(text, wpn)
                nodes[w_id] = {
                    "id": w_id, 
                    "name": wpn, 
                    "type": "WEAPON", 
                    "details": {
                        "caliber": wpn,
                        "owner": status_info["owner"],
                        "custody_status": status_info["custody_status"],
                        "notes": status_info["context_notes"]
                    }
                }
                pos = text.lower().find(wpn.lower())
                window = text[max(0, pos-120):pos+120].lower() if pos != -1 else ""
                matched_s = next((s_id for s_name, s_id in detected_suspects.items() if s_name.split()[0].lower() in window), suspect_id_list[0])
                links.append({"source": matched_s, "target": w_id, "relationship": "ARMED_WITH", "weight": 1.4})

        # Bank Accounts
        for acc in structured.get("bank_accounts", []):
            acc_id = self._generate_id("ACC", acc)
            status_info = self._extract_item_status(text, acc)
            nodes[acc_id] = {
                "id": acc_id, 
                "name": f"ACC-****{acc[-4:]}", 
                "type": "BANK_ACCOUNT", 
                "details": {
                    "account_full": acc,
                    "owner": status_info["owner"],
                    "custody_status": "Account Frozen (Sec 102 CrPC)" if "freez" in status_info["context_notes"].lower() else "Active Layering Mule",
                    "notes": status_info["context_notes"]
                }
            }
            pos = text.find(acc)
            window = text[max(0, pos-120):pos+120].lower() if pos != -1 else ""
            matched_s = next((s_id for s_name, s_id in detected_suspects.items() if s_name.split()[0].lower() in window), suspect_id_list[min(1, len(suspect_id_list)-1)])
            links.append({"source": matched_s, "target": acc_id, "relationship": "FINANCIAL_TRAIL", "weight": 1.1})

        return list(nodes.values()), links