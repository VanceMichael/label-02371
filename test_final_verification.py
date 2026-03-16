#!/usr/bin/env python3
"""
最终验证测试脚本：验证所有6个bug修复
"""
import requests
import json
import threading
import time
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8088/api"
USER_CREDENTIALS = {"username": "zhangsan", "password": "123456"}

# 全局变量用于并发测试
results = []
success_count = 0
conflict_count = 0
error_count = 0
lock = threading.Lock()

def get_auth_token():
    """获取认证token"""
    response = requests.post(f"{BASE_URL}/auth/login", json=USER_CREDENTIALS)
    if response.status_code == 200:
        return response.json().get("data", {}).get("token")
    raise Exception(f"登录失败: {response.text}")

def get_room_id(token):
    """获取一个可用的房间ID"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/rooms?page=1&pageSize=10", headers=headers)
    if response.status_code == 200:
        data = response.json().get("data", {})
        rooms = data.get("records", [])
        if rooms:
            return rooms[0]["id"]
    raise Exception(f"获取房间列表失败: {response.text}")

def test_api_validation(token, room_id):
    """测试API验证逻辑 (Bug 2 & Bug 4)"""
    print("\n" + "="*60)
    print("测试 1: API 参数验证")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    test_cases = [
        {
            "name": "离店日期 = 入住日期",
            "data": {"roomId": room_id, "checkInDate": today, "checkOutDate": today},
            "expected_status": 400,
            "expected_msg": "晚于"
        },
        {
            "name": "离店日期 < 入住日期",
            "data": {"roomId": room_id, "checkInDate": day_after, "checkOutDate": tomorrow},
            "expected_status": 400,
            "expected_msg": "晚于"
        },
        {
            "name": "入住日期 < 今天",
            "data": {"roomId": room_id, "checkInDate": yesterday, "checkOutDate": tomorrow},
            "expected_status": 400,
            "expected_msg": "今天"
        },
        {
            "name": "正常预订",
            "data": {"roomId": room_id, "checkInDate": tomorrow, "checkOutDate": day_after},
            "expected_status": 200,
            "expected_msg": None
        }
    ]
    
    all_passed = True
    for tc in test_cases:
        response = requests.post(f"{BASE_URL}/bookings", json=tc["data"], headers=headers)
        resp_data = response.json()
        status = response.status_code
        msg = resp_data.get("message", "")
        
        passed = status == tc["expected_status"]
        if tc["expected_msg"]:
            passed = passed and (tc["expected_msg"] in msg)
        
        status_icon = "✅" if passed else "❌"
        print(f"{status_icon} {tc['name']}: 预期={tc['expected_status']}, 实际={status}")
        if not passed:
            print(f"   响应: {msg}")
            all_passed = False
    
    return all_passed

def test_duplicate_booking(token, room_id):
    """测试重复预订 (Bug 6)"""
    print("\n" + "="*60)
    print("测试 2: 重复预订检测")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    check_in = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
    check_out = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    # 第一次预订
    data = {"roomId": room_id, "checkInDate": check_in, "checkOutDate": check_out}
    response = requests.post(f"{BASE_URL}/bookings", json=data, headers=headers)
    print(f"第一次预订: 状态={response.status_code}")
    
    # 重复预订
    response2 = requests.post(f"{BASE_URL}/bookings", json=data, headers=headers)
    status2 = response2.status_code
    msg2 = response2.json().get("message", "")
    
    passed = status2 == 409
    status_icon = "✅" if passed else "❌"
    print(f"{status_icon} 重复预订: 预期=409, 实际={status2}")
    if not passed:
        print(f"   响应: {msg2}")
    
    return passed

def concurrent_booking_thread(token, room_id, check_in, check_out, thread_id):
    """并发预订线程函数"""
    global success_count, conflict_count, error_count
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "roomId": room_id, 
        "checkInDate": check_in, 
        "checkOutDate": check_out,
        "remark": f"并发测试 - 线程{thread_id}"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/bookings", json=data, headers=headers, timeout=10)
        status = response.status_code
        
        with lock:
            results.append({
                "thread": thread_id,
                "status": status,
                "response": response.json()
            })
            
            if status == 200:
                success_count += 1
            elif status == 409:
                conflict_count += 1
            else:
                error_count += 1
    except Exception as e:
        with lock:
            error_count += 1
            results.append({
                "thread": thread_id,
                "status": -1,
                "error": str(e)
            })

def test_concurrent_bookings(token, room_id):
    """测试并发预订 (Bug 6)"""
    global success_count, conflict_count, error_count, results
    success_count = 0
    conflict_count = 0
    error_count = 0
    results = []
    
    print("\n" + "="*60)
    print("测试 3: 高并发防重复预订")
    print("="*60)
    
    check_in = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    check_out = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")
    
    # 30个并发线程
    thread_count = 30
    threads = []
    
    print(f"启动 {thread_count} 个并发线程...")
    start_time = time.time()
    
    for i in range(thread_count):
        t = threading.Thread(target=concurrent_booking_thread, 
                           args=(token, room_id, check_in, check_out, i+1))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    end_time = time.time()
    print(f"测试完成，耗时: {end_time - start_time:.2f}秒")
    print(f"成功: {success_count}, 冲突: {conflict_count}, 错误: {error_count}")
    
    # 验证数据库中只有一条记录
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/bookings?page=1&pageSize=50", headers=headers)
    bookings = response.json().get("data", {}).get("records", [])
    
    # 统计同一天的有效预订（状态：0待确认、1已确认、2已入住）
    same_bookings = [b for b in bookings if b.get("checkInDate") == check_in and b.get("roomId") == room_id and b.get("status") in [0, 1, 2]]
    print(f"数据库中同一房间同一日期的有效预订数: {len(same_bookings)}")
    
    # 应该只有一个成功
    passed = success_count == 1 and len(same_bookings) == 1
    status_icon = "✅" if passed else "❌"
    
    if passed:
        print(f"{status_icon} 并发测试通过! 只有1个预订成功，其余被正确阻止")
    else:
        print(f"{status_icon} 并发测试失败!")
        if success_count > 1:
            print(f"   错误: 有 {success_count} 个预订成功了!")
        if len(same_bookings) > 1:
            print(f"   错误: 数据库中有 {len(same_bookings)} 条重复记录!")
    
    # 打印错误详情
    if error_count > 0:
        print("\n错误详情:")
        for r in results:
            if r.get("status") not in [200, 409]:
                print(f"  线程{r['thread']}: {r}")
    
    return passed

def check_booking_count(token, room_id, check_in):
    """检查数据库中预订数量"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/bookings?page=1&pageSize=100", headers=headers)
    if response.status_code == 200:
        bookings = response.json().get("data", {}).get("records", [])
        same_bookings = [b for b in bookings if b.get("checkInDate") == check_in and b.get("roomId") == room_id and b.get("status") in [0, 1, 2]]
        return len(same_bookings)
    return -1

def cancel_test_bookings(token, room_id):
    """取消测试预订"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/bookings?page=1&pageSize=50", headers=headers)
    if response.status_code == 200:
        bookings = response.json().get("data", {}).get("records", [])
        for booking in bookings:
            remark = booking.get("remark") or ""
            if booking.get("roomId") == room_id and booking.get("status") in [0, 1]:
                if "并发测试" in remark or "测试" in remark or len(remark) < 20:
                    cancel_response = requests.put(f"{BASE_URL}/bookings/{booking['id']}/cancel", headers=headers)
                    print(f"取消预订 {booking['id']}: {cancel_response.status_code}")

def main():
    try:
        print("🚀 开始最终验证测试...")
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. 获取token
        token = get_auth_token()
        print(f"✅ 获取认证token成功")
        
        # 2. 获取房间ID
        room_id = get_room_id(token)
        print(f"✅ 获取房间ID成功: {room_id}")
        
        # 3. 取消之前的测试预订
        cancel_test_bookings(token, room_id)
        
        # 4. 运行测试
        test1_passed = test_api_validation(token, room_id)
        time.sleep(1)
        
        test2_passed = test_duplicate_booking(token, room_id)
        time.sleep(1)
        
        # 清理后再进行并发测试
        cancel_test_bookings(token, room_id)
        time.sleep(1)
        
        test3_passed = test_concurrent_bookings(token, room_id)
        
        # 5. 总结
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        
        all_tests = [
            ("API参数验证", test1_passed),
            ("重复预订检测", test2_passed),
            ("高并发防重复预订", test3_passed),
        ]
        
        passed_count = sum(1 for _, p in all_tests if p)
        total_count = len(all_tests)
        
        for name, passed in all_tests:
            icon = "✅" if passed else "❌"
            print(f"{icon} {name}")
        
        print(f"\n结果: {passed_count}/{total_count} 测试通过")
        
        if passed_count == total_count:
            print("\n🎉 所有测试通过!")
        else:
            print("\n⚠️  部分测试失败!")
            return 1
        
        # 清理测试数据
        cancel_test_bookings(token, room_id)
        
        return 0
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
