import os
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
from typesafe_sdk import TypeSafeClient, Noul, NoulCriteria

config_path = Path(__file__).resolve().parents[2] / "local_paths.json"
try:
    with open(config_path, "r", encoding="utf-8") as f:
        PATHS_CONFIG = json.load(f)
except Exception:
    PATHS_CONFIG = {}

class HistoryScorer:
    def __init__(self, api_key: str | None = None, model: str | None = None, max_workers: int = 10):
        self.api_key = api_key or os.getenv("TYPESAFE_API_KEY") or PATHS_CONFIG.get("TYPESAFE_API_KEY")
        self.model = model or PATHS_CONFIG.get("RERANKER_MODEL", "jev-latest")
        self.max_workers = max_workers
        self.client = TypeSafeClient(api_key=self.api_key, timeout=20.0) if self.api_key else None
        
        self.relevance_question = Noul(
            instructions=(
                "Đánh giá mức độ liên quan (relevance score từ 0.0 đến 1.0) giữa tin nhắn lịch sử và câu hỏi hiện tại của người dùng. "
                "ĐẶC BIỆT LƯU Ý: Nếu câu hỏi hiện tại có ý đề cập, ám chỉ hoặc quy chiếu tới thông tin trước đó "
                "(như nhưng không giới hạn ở: 'phần trên', 'thứ 2', 'trước đó', 'vừa rồi', 'ở trên', 'cái này', 'gói đó', 'các gói vừa nêu'...), "
                "hãy ĐẶC BIỆT ƯU TIÊN và cho điểm cao đối với các tin nhắn có vị trí gần câu hỏi hiện tại nhất (ví dụ: 1 hoặc 2 tin nhắn trước)."
            ),
            criteria=NoulCriteria(
                true="Tin nhắn lịch sử có nội dung liên quan trực tiếp, cung cấp dữ liệu giải đáp hoặc là đối tượng ngữ cảnh mà câu hỏi hiện tại đang quy chiếu tới.",
                false="Tin nhắn lịch sử không liên quan đến câu hỏi hiện tại hoặc thuộc về một chủ đề/ngữ cảnh hoàn toàn khác."
            )
        )

    def format_turn_content(self, turn: Dict[str, Any]) -> str:
        parts = [f"User: {turn.get('user_query', '').strip()}"]
        tool_out = turn.get('tool_output', '').strip()
        if tool_out:
            # Rút gọn nhẹ nếu tool output quá dài để tối ưu độ trễ Jev
            if len(tool_out) > 3000:
                tool_out = tool_out[:3000] + "\n... (đã rút gọn dữ liệu tra cứu)"
            parts.append(f"Tool Output:\n{tool_out}")
        ai_out = turn.get('agent_output', '').strip()
        if ai_out:
            parts.append(f"AI: {ai_out}")
        return "\n".join(parts)

    def score_single(self, current_query: str, turn: Dict[str, Any], diff: int) -> float:
        if not self.client:
            print("[HistoryScorer] Chưa cấu hình TYPESAFE_API_KEY.")
            return 0.0
        
        content = self.format_turn_content(turn)
        state = {
            "current_query": current_query,
            "current_query_position": "Câu hỏi hiện tại",
            "historical_message_position": f"{diff} message trước câu hỏi hiện tại",
            "historical_message_content": content
        }
        try:
            resp = self.client.system_one(
                state=state,
                questions={"relevance": self.relevance_question},
                model=self.model
            )
            score = float(resp.nouls["relevance"].noul)
            return round(score, 4)
        except Exception as e:
            print(f"[HistoryScorer Error] Message {turn.get('id')}: {e}")
            return 0.0

    def evaluate_recent_history(
        self,
        current_query: str,
        recent_turns: List[Dict[str, Any]],
        r_matrix: Dict[Tuple[int, int], float],
        a: float = 0.5,
        threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Đánh giá mức độ tương đồng giữa current_query và tối đa 10 message gần nhất.
        recent_turns: danh sách message theo thứ tự thời gian tăng dần (cũ -> mới).
        """
        m = len(recent_turns)
        if m == 0:
            debug_text = "**[Đánh giá tương đồng lịch sử (Jev)]**\n- Số lượng message đánh giá: 0 (Hội thoại mới bắt đầu)\n"
            return {
                "scored_messages": [],
                "valid_context": [],
                "context_text": "",
                "debug_text": debug_text
            }

        # 1. Tính d_i song song bằng ThreadPoolExecutor
        # Với recent_turns[k], vị trí cách query hiện tại là (m - k) message trước
        indexed_items = []
        for k, turn in enumerate(recent_turns):
            diff = m - k
            indexed_items.append((turn, diff))

        def _worker(item):
            turn, diff = item
            d_i = self.score_single(current_query, turn, diff)
            return turn, diff, d_i

        with ThreadPoolExecutor(max_workers=min(self.max_workers, m)) as pool:
            score_results = list(pool.map(_worker, indexed_items))

        # 2. Tính toán cập nhật u_i theo công thức Harmonic Bridge
        # u_i = a * d_i + (1 - a) * average_by_j(d_bridge_ij)
        # với d_bridge_ij = 2 * d_i * r_ij / (d_i + r_ij)
        scored_messages = []
        turn_map = {item[0]["id"]: item for item in score_results}

        for turn, diff, d_i in score_results:
            turn_id = turn["id"]
            r_ij_list = []
            bridge_list = []

            for other_turn, other_diff, other_d_i in score_results:
                other_id = other_turn["id"]
                if other_id == turn_id:
                    continue
                r_val = r_matrix.get((turn_id, other_id), r_matrix.get((other_id, turn_id), 0.0))
                r_ij_list.append((other_id, other_diff, round(r_val, 4)))

                denom = d_i + r_val
                if denom > 0:
                    d_bridge = 2.0 * d_i * r_val / denom
                else:
                    d_bridge = 0.0
                bridge_list.append(d_bridge)

            if bridge_list:
                avg_bridge = sum(bridge_list) / len(bridge_list)
                u_i = a * d_i + (1.0 - a) * avg_bridge
            else:
                avg_bridge = d_i
                u_i = d_i

            u_i = round(u_i, 4)
            scored_messages.append({
                "turn": turn,
                "turn_id": turn_id,
                "diff": diff,
                "d_i": d_i,
                "r_ij_list": r_ij_list,
                "avg_bridge": round(avg_bridge, 4),
                "u_i": u_i,
                "passed": u_i >= threshold
            })

        # 3. Lọc các message đạt ngưỡng score >= 0.7 làm context cho LLM
        # Sắp xếp các message hợp lệ: ưu tiên theo thứ tự gần nhất (diff nhỏ nhất) hoặc score cao nhất
        valid_messages = [item for item in scored_messages if item["passed"]]
        # Giữ thứ tự thời gian tự nhiên cho context
        valid_messages_sorted = sorted(valid_messages, key=lambda x: x["turn"]["id"])

        context_blocks = []
        for item in valid_messages_sorted:
            turn = item["turn"]
            diff = item["diff"]
            u_score = item["u_i"]
            
            block_lines = [f"- Tin nhắn ({diff} message trước | Độ tương đồng: {u_score:.4f}):"]
            block_lines.append(f"  User: {turn.get('user_query', '')}")
            if turn.get("tool_output"):
                block_lines.append(f"  [Kết quả tra cứu trước đó]:\n{turn['tool_output']}")
            block_lines.append(f"  AI: {turn.get('agent_output', '')}")
            context_blocks.append("\n".join(block_lines))

        context_text = "\n\n".join(context_blocks)

        # 4. Soạn thông tin debug ngắn gọn ra frontend phần thinking
        debug_lines = [
            f"**[Đánh giá tương đồng lịch sử (Jev)]**",
            f"- Số lượng message đánh giá: {m}"
        ]
        # In các message từ gần nhất đến xa nhất (hoặc theo thứ tự diff)
        for idx, item in enumerate(scored_messages, 1):
            diff = item["diff"]
            turn_id = item["turn_id"]
            d_val = item["d_i"]
            u_val = item["u_i"]
            r_list = item["r_ij_list"]
            if r_list:
                r_repr = "[" + ", ".join([f"Msg {oid} ({d}msg trước): {r}" for oid, d, r in r_list]) + "]"
            else:
                r_repr = "Không có"
            
            status = "✓ ĐẠT (>= 0.7)" if item["passed"] else "✗ (< 0.7)"
            debug_lines.append(
                f"- Message {turn_id} ({diff} message trước): d_i={d_val:.4f} | r_ij={r_repr} | u_i={u_val:.4f} -> {status}"
            )

        debug_text = "\n".join(debug_lines) + "\n"

        return {
            "scored_messages": scored_messages,
            "valid_context": valid_messages_sorted,
            "context_text": context_text,
            "debug_text": debug_text
        }

_scorer_instance = None

def get_history_scorer() -> HistoryScorer:
    global _scorer_instance
    if _scorer_instance is None:
        _scorer_instance = HistoryScorer()
    return _scorer_instance
