import json
import os
import hashlib
from pathlib import Path

def generate_encoded_id(name: str) -> str:
    """生成唯一的 8 位字符编码"""
    return hashlib.md5(name.encode('utf-8')).hexdigest()[:8].upper()

def load_json_file(file_path: Path):
    if not file_path.exists():
        print(f"⚠️ 警告: 找不到文件 {file_path}")
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        if isinstance(data, dict):
            return data.get('items', [])
        return data

def convert_world_data_to_ak(session_id: str, project_root: str):
    project_path = Path(project_root)
    
    # 1. 路径定位
    semantic_dir = project_path / "examples" / "WorldKernel" / "templates" / session_id / "generated" / "artifacts" / "semantic"
    characters_json_path = semantic_dir / "characters" / "characters.json"
    relations_json_path = semantic_dir / "relation_graph" / "relation_graph.json"

    # 2. 输出路径
    output_base_dir = project_path / "examples" / "WorldKernel" / "data"
    agents_out_dir = output_base_dir / "agents"
    relations_out_dir = output_base_dir / "relations"
    
    os.makedirs(agents_out_dir, exist_ok=True)
    os.makedirs(relations_out_dir, exist_ok=True)

    # ==================== Part A: 转换角色数据并建立翻译字典 ====================
    print(f"🔄 正在读取人物文件: {characters_json_path}")
    characters_raw = load_json_file(characters_json_path)
    
    profiles_lines = []
    states_lines = []
    
    # 💡 核心修复：建立 ID 到 名字 的翻译字典
    id_to_name = {}

    for char in characters_raw:
        identity = char.get("identity", {})
        state = char.get("state", {})
        
        char_id = identity.get("id")
        name = identity.get("name")
        
        if not name or name == "未知实体":
            continue
            
        # 将 ID 和名字绑定
        if char_id:
            id_to_name[char_id] = name

        char_code = generate_encoded_id(name)
        profiles_lines.append({"code": char_code, "id": name})

        # 修复位置解析：大模型里的 location 是一个嵌套对象
        loc_data = state.get("location", {})
        loc_str = loc_data.get("location_id", "未知地点") if isinstance(loc_data, dict) else loc_data

        states_lines.append({
            "id": name,
            "health": 5,                                      
            "location": loc_str,     
            "gender": identity.get("gender", "未知"),          
            "duty": identity.get("role", "居民"),              
            "character": identity.get("description", ""),      
            "right": 1,                                       
            "appearance_round": 1,                            
            "death_round": 999                                
        })

    with open(agents_out_dir / "profiles_test.jsonl", 'w', encoding='utf-8') as f:
        for p in profiles_lines:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')

    with open(agents_out_dir / "states.jsonl", 'w', encoding='utf-8') as f:
        for s in states_lines:
            f.write(json.dumps(s, ensure_ascii=False) + '\n')

    print(f"   └─ 已生成 profiles_test.jsonl ({len(profiles_lines)} 条)")
    print(f"   └─ 已生成 states.jsonl ({len(states_lines)} 条)")

    # ==================== Part B: 转换关系并翻译回中文 ====================
    print(f"🔄 正在读取关系文件: {relations_json_path}")
    relations_raw = load_json_file(relations_json_path)
    relations_lines = []
    
    for rel in relations_raw:
        edge = rel.get("edge", {})
        
        # 💡 核心修复：读取正确的 from_id 和 to_id 字段
        from_id = edge.get("from_id")
        to_id = edge.get("to_id")
        rel_type = edge.get("type", "认识")

        if not from_id or not to_id:
            continue

        # 💡 核心修复：用字典把代号（e:xxx:char:xxx）翻译成中文名字
        source_name = id_to_name.get(from_id, from_id)
        target_name = id_to_name.get(to_id, to_id)

        relations_lines.append({
            "source": source_name,
            "target": target_name,
            "relation": rel_type,
            "start_round": 1  
        })

    with open(relations_out_dir / "relations.jsonl", 'w', encoding='utf-8') as f:
        for r in relations_lines:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    print(f"   └─ 已生成 relations.jsonl ({len(relations_lines)} 条)")

    print(f"\n✅ 适配转换完成！成功转换 {len(profiles_lines)} 名角色和 {len(relations_lines)} 条社会关系。")

if __name__ == "__main__":
    # 填入用于测试的 Session ID
    CURRENT_SESSION = "f2a1a0cd-7282-416d-871f-1dfc21cc1351" 
    
    # 动态获取 OpenStory 的项目根目录 (根据 ak_adapter.py 所在的层级向上推算)
    # 假设该文件在 examples/WorldKernel/src/worldkernel/integrations/ 目录下
    current_file_path = os.path.abspath(__file__)
    ROOT_DIR = os.path.abspath(os.path.join(current_file_path, "..", "..", "..", "..", "..", ".."))
    
    print(f"🚀 正在启动 WorldKernel -> Agent-Kernel 适配器管道...")
    convert_world_data_to_ak(CURRENT_SESSION, ROOT_DIR)