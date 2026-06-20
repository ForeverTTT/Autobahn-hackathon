"""
Knowledge Graph
知识图谱的存储和查询
"""
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json

from .entities import (
    Node, Edge, NodeType, EdgeType,
    RoadNode, SegmentNode, DateNode, EventNode,
    WeatherNode, CongestionNode, UserNode
)

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


class KnowledgeGraph:
    """
    交通知识图谱
    支持NetworkX（内存）或Neo4j（持久化）后端
    """

    def __init__(self, backend: str = "networkx"):
        self.backend = backend
        self._nodes: Dict[str, Node] = {}
        self._edges: List[Edge] = []

        if backend == "networkx" and HAS_NETWORKX:
            self._graph = nx.DiGraph()
        else:
            self._graph = None

    def add_node(self, node: Node) -> bool:
        """添加节点"""
        self._nodes[node.id] = node

        if self._graph is not None:
            self._graph.add_node(
                node.id,
                type=node.type.value,
                **node.properties
            )

        return True

    def add_edge(self, edge: Edge) -> bool:
        """添加边"""
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            return False

        self._edges.append(edge)

        if self._graph is not None:
            self._graph.add_edge(
                edge.source_id,
                edge.target_id,
                type=edge.type.value,
                weight=edge.weight,
                **edge.properties
            )

        return True

    def get_node(self, node_id: str) -> Optional[Node]:
        """获取节点"""
        return self._nodes.get(node_id)

    def get_nodes_by_type(self, node_type: NodeType) -> List[Node]:
        """按类型获取节点"""
        return [n for n in self._nodes.values() if n.type == node_type]

    def get_neighbors(
        self,
        node_id: str,
        edge_type: EdgeType = None,
        direction: str = "outgoing"
    ) -> List[Tuple[Node, Edge]]:
        """获取邻居节点"""
        results = []

        for edge in self._edges:
            if direction == "outgoing" and edge.source_id == node_id:
                if edge_type is None or edge.type == edge_type:
                    neighbor = self._nodes.get(edge.target_id)
                    if neighbor:
                        results.append((neighbor, edge))

            elif direction == "incoming" and edge.target_id == node_id:
                if edge_type is None or edge.type == edge_type:
                    neighbor = self._nodes.get(edge.source_id)
                    if neighbor:
                        results.append((neighbor, edge))

            elif direction == "both":
                if edge.source_id == node_id:
                    if edge_type is None or edge.type == edge_type:
                        neighbor = self._nodes.get(edge.target_id)
                        if neighbor:
                            results.append((neighbor, edge))
                elif edge.target_id == node_id:
                    if edge_type is None or edge.type == edge_type:
                        neighbor = self._nodes.get(edge.source_id)
                        if neighbor:
                            results.append((neighbor, edge))

        return results

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5
    ) -> List[List[str]]:
        """查找两节点间的路径"""
        if self._graph is not None:
            try:
                paths = list(nx.all_simple_paths(
                    self._graph, source_id, target_id, cutoff=max_depth
                ))
                return paths
            except nx.NetworkXNoPath:
                return []
        else:
            # 简单BFS实现
            return self._bfs_paths(source_id, target_id, max_depth)

    def _bfs_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int
    ) -> List[List[str]]:
        """BFS查找路径"""
        if source_id == target_id:
            return [[source_id]]

        paths = []
        queue = [(source_id, [source_id])]

        while queue:
            current, path = queue.pop(0)

            if len(path) > max_depth:
                continue

            neighbors = self.get_neighbors(current, direction="outgoing")

            for neighbor, _ in neighbors:
                if neighbor.id == target_id:
                    paths.append(path + [neighbor.id])
                elif neighbor.id not in path:
                    queue.append((neighbor.id, path + [neighbor.id]))

        return paths

    def query_subgraph(
        self,
        center_node_id: str,
        depth: int = 2
    ) -> Dict[str, Any]:
        """查询以某节点为中心的子图"""
        visited_nodes = set()
        visited_edges = []
        queue = [(center_node_id, 0)]

        while queue:
            node_id, current_depth = queue.pop(0)

            if node_id in visited_nodes or current_depth > depth:
                continue

            visited_nodes.add(node_id)

            if current_depth < depth:
                neighbors = self.get_neighbors(node_id, direction="both")
                for neighbor, edge in neighbors:
                    visited_edges.append(edge)
                    if neighbor.id not in visited_nodes:
                        queue.append((neighbor.id, current_depth + 1))

        return {
            "nodes": [self._nodes[nid].to_dict() for nid in visited_nodes if nid in self._nodes],
            "edges": [e.to_dict() for e in visited_edges],
        }

    def get_statistics(self) -> Dict[str, Any]:
        """获取图统计信息"""
        type_counts = {}
        for node in self._nodes.values():
            type_name = node.type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        edge_type_counts = {}
        for edge in self._edges:
            type_name = edge.type.value
            edge_type_counts[type_name] = edge_type_counts.get(type_name, 0) + 1

        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "node_types": type_counts,
            "edge_types": edge_type_counts,
        }

    def to_json(self) -> str:
        """导出为JSON"""
        return json.dumps({
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges],
        }, indent=2, ensure_ascii=False)

    def clear(self) -> None:
        """清空图"""
        self._nodes.clear()
        self._edges.clear()
        if self._graph is not None:
            self._graph.clear()
