import networkx as nx
import community.community_louvain as community_louvain
from typing import List, Dict, Any
from app.services.ml_service import MLForensicsService

class GraphEngineService:
    def __init__(self):
        self.graph = nx.Graph()
        self.ml_service = MLForensicsService()

    def construct_graph(self, nodes: List[Dict[str, Any]], links: List[Dict[str, Any]]) -> None:
        self.graph.clear()
        for node in nodes:
            self.graph.add_node(node["id"], **node)
        for link in links:
            self.graph.add_edge(
                link["source"], 
                link["target"], 
                relationship=link.get("relationship", "CONNECTED"),
                label=link.get("relationship", "CONNECTED"),
                weight=link.get("weight", 1.0)
            )

    def analyze_and_score(self) -> Dict[str, Any]:
        if len(self.graph.nodes) == 0:
            return {"nodes": [], "links": [], "stats": {"total_entities": 0, "total_connections": 0, "detected_syndicates": 0, "critical_threat_nodes": 0}}

        degree_cen = nx.degree_centrality(self.graph)
        between_cen = nx.betweenness_centrality(self.graph)
        try:
            pagerank_cen = nx.pagerank(self.graph, alpha=0.85, weight="weight")
        except Exception:
            pagerank_cen = degree_cen

        try:
            partition = community_louvain.best_partition(self.graph)
        except Exception:
            partition = {n: 0 for n in self.graph.nodes}

        formatted_nodes = []
        for n_id, data in self.graph.nodes(data=True):
            b_score = between_cen.get(n_id, 0.0)
            p_score = pagerank_cen.get(n_id, 0.0)
            d_score = degree_cen.get(n_id, 0.0)
            
            node_type = data.get("type", "PERSON")
            is_critical_flag = data.get("details", {}).get("is_critical", False)
            sections = data.get("details", {}).get("sections", [])
            
            # Feed real extracted legal features into the ML Forensics Model
            if node_type == "PERSON":
                ml_features = {
                    "network_degree": int(self.graph.degree(n_id)),
                    "network_betweenness": float(b_score),
                    "topological_kingpin_score": float(p_score),
                    "organized_operation_indicator": 1 if is_critical_flag else 0,
                    "property_offence_indicator": 1 if any(sec in str(sections) for sec in ["392", "379", "411"]) else 0,
                    "ipc_392": 1 if "392" in str(sections) else 0,
                    "ipc_379": 1 if "379" in str(sections) else 0,
                    "ipc_411": 1 if "411" in str(sections) else 0,
                    "physical_force_used": 1 if "392" in str(sections) else 0,
                    "court_level_High Court": 1 if "High Court" in data.get("details", {}).get("extracted_text", "") else 0,
                    "case_type_Writ Petition (Detention)": 1 if "Writ Petition" in data.get("details", {}).get("extracted_text", "") else 0,
                    "number_of_accused": len([n for n in self.graph.nodes if "PERSON" in str(n)]),
                    "unauthorized_transfer_amount_inr": 5000000.0 if is_critical_flag else 0.0
                }
                ml_intel = self.ml_service.predict_entity_intelligence(ml_features)
                composite_risk = ml_intel["ml_syndicate_probability"]
                ml_role = ml_intel["predicted_role"]
                conviction = f"{ml_intel['conviction_propensity'] * 100:.1f}%"
                bail = ml_intel["bail_eligibility"]
            else:
                ml_role = None
                conviction = "N/A"
                bail = "N/A"
                if node_type == "CRIME_FIR":
                    composite_risk = 0.50
                elif node_type == "POLICE_STATION":
                    composite_risk = 0.10
                elif node_type == "WEAPON":
                    composite_risk = 0.85
                elif node_type == "BANK_ACCOUNT":
                    composite_risk = 0.45
                elif node_type == "PHONE":
                    composite_risk = 0.35
                elif node_type == "VEHICLE":
                    composite_risk = 0.30
                else:
                    composite_risk = 0.20

            # Distinct Color Assignments
            if node_type == "PERSON" and (composite_risk >= 0.70 or is_critical_flag):
                color = "#ef4444"  # Red (Critical Threat)
                size = 24
            elif node_type == "PERSON":
                color = "#a855f7"  # Purple (Suspects)
                size = 18
            elif node_type == "CRIME_FIR":
                color = "#f43f5e"  # Rose Pink (Registered Crime FIRs)
                size = 16
            elif node_type == "POLICE_STATION":
                color = "#14b8a6"  # Teal Cyan (Police Stations)
                size = 16
            elif node_type == "PHONE":
                color = "#06b6d4"  # Cyan (Phones)
                size = 11
            elif node_type == "BANK_ACCOUNT":
                color = "#10b981"  # Emerald Green (Bank Accounts)
                size = 13
            elif node_type == "VEHICLE":
                color = "#6366f1"  # Indigo (Vehicles)
                size = 13
            elif node_type == "WEAPON":
                color = "#f59e0b"  # Amber (Weapons)
                size = 15
            else:
                color = "#94a3b8"
                size = 10

            formatted_nodes.append({
                "id": n_id,
                "name": data.get("name", n_id),
                "type": node_type,
                "risk_score": composite_risk,
                "color": color,
                "size": size,
                "cluster": f"Syndicate-{partition.get(n_id, 0) + 1}",
                "details": {
                    **data.get("details", {}),
                    "betweenness": round(b_score, 4),
                    "pagerank": round(p_score, 4),
                    "degree": round(d_score, 4),
                    "ml_role": ml_role,
                    "conviction_propensity": conviction,
                    "bail_eligibility": bail
                }
            })

        formatted_links = []
        for u, v, link_data in self.graph.edges(data=True):
            formatted_links.append({
                "source": u,
                "target": v,
                "relationship": link_data.get("relationship", "ASSOCIATED_WITH"),
                "label": link_data.get("label", "CONNECTED"),
                "weight": link_data.get("weight", 1.0)
            })

        critical_count = len([n for n in formatted_nodes if n["type"] == "PERSON" and (n["color"] == "#ef4444" or n["risk_score"] >= 0.70)])

        return {
            "nodes": formatted_nodes,
            "links": formatted_links,
            "stats": {
                "total_entities": len(formatted_nodes),
                "total_connections": len(formatted_links),
                "detected_syndicates": len(set(partition.values())),
                "critical_threat_nodes": critical_count
            }
        }