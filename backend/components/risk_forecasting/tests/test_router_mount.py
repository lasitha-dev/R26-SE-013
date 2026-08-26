import ast
import os
from pathlib import Path

def get_main_ast():
    main_path = Path(__file__).resolve().parents[3] / "main.py"
    assert main_path.exists(), f"Cannot find main.py at {main_path}"
    
    with open(main_path, "r", encoding="utf-8") as f:
        source = f.read()
    
    return ast.parse(source)

def test_static_router_mount():
    tree = get_main_ast()
    
    # 2. Check import
    imported = False
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "components.risk_forecasting.routes":
            for alias in node.names:
                if alias.name == "router" and alias.asname == "risk_forecasting_router":
                    imported = True
    assert imported, "risk_forecasting_router is not imported properly"

    # Find create_app
    create_app_node = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "create_app":
            create_app_node = node
            break
            
    assert create_app_node is not None, "create_app function not found"
    
    sd_mounted = False
    health_mounted = False
    risk_mounted_count = 0
    demo_mounted = False
    
    for stmt in create_app_node.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "include_router":
                if not call.args:
                    continue
                arg_id = getattr(call.args[0], "id", None)
                
                if arg_id == "sd_router":
                    sd_mounted = True
                elif arg_id == "health_anomaly_router":
                    for keyword in call.keywords:
                        if keyword.arg == "prefix" and getattr(keyword.value, "value", None) == "/api":
                            health_mounted = True
                elif arg_id == "risk_forecasting_router":
                    risk_mounted_count += 1
                    prefix_match = False
                    tags_match = False
                    for keyword in call.keywords:
                        if keyword.arg == "prefix" and getattr(keyword.value, "value", None) == "/api/v1/risk-forecasting":
                            prefix_match = True
                        if keyword.arg == "tags":
                            if isinstance(keyword.value, ast.List):
                                elts = keyword.value.elts
                                if len(elts) == 1 and getattr(elts[0], "value", None) == "Risk Forecasting":
                                    tags_match = True
                    assert prefix_match, "Prefix for risk_forecasting_router is incorrect"
                    assert tags_match, "Tags for risk_forecasting_router are incorrect"
                elif arg_id and "demo" in arg_id.lower():
                    demo_mounted = True
    
    assert risk_mounted_count == 1, f"risk_forecasting_router is mounted {risk_mounted_count} times, expected exactly 1"
    assert sd_mounted, "sd_router is not mounted"
    assert health_mounted, "health_anomaly_router is not mounted with /api"
    assert not demo_mounted, "Demo router is unexpectedly mounted"

