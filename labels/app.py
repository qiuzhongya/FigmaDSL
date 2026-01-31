from flask import Flask, render_template, jsonify, request
import json
import os

app = Flask(__name__)

# 数据文件路径
DATA_FILE = '../tmp/diff.json'

def load_data():
    """加载图片比对数据"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_data(data):
    """保存图片比对数据"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    """主页面 - 显示所有图片比对数据"""
    return render_template('index.html')

@app.route('/comparison/<int:comparison_id>')
def comparison_detail(comparison_id):
    """详情页面 - 显示特定比对的完整信息"""
    return render_template('comparison_detail.html', comparison_id=comparison_id)

@app.route('/api/comparisons')
def get_all_comparisons():
    """API: 获取所有比对数据"""
    data = load_data()
    return jsonify(data)

@app.route('/api/comparisons/<int:comparison_id>')
def get_comparison(comparison_id):
    """API: 获取特定比对数据"""
    data = load_data()
    for item in data:
        if item.get('id') == comparison_id:
            return jsonify(item)
    return jsonify({'error': '未找到指定的比对数据'}), 404

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': '页面未找到'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': '服务器内部错误'}), 500

if __name__ == '__main__':
    # 如果数据文件不存在，创建示例数据
    if not os.path.exists(DATA_FILE):
        sample_data = [
            {
                "id": 1,
                "a": "https://via.placeholder.com/400x300/FF6B6B/FFFFFF?text=Image+A1",
                "b": "https://via.placeholder.com/400x300/4ECDC4/FFFFFF?text=Image+B1",
                "diff": "这是第一组图片的详细差异分析。图片A显示了红色背景的占位符图像，而图片B显示了青色背景的占位符图像。两张图片在颜色、布局和文字内容方面存在明显差异。具体差异包括：\n\n1. 背景颜色：A图为红色(#FF6B6B)，B图为青色(#4ECDC4)\n2. 文字内容：A图显示'Image A1'，B图显示'Image B1'\n3. 整体视觉效果：两张图片呈现完全不同的视觉风格"
            },
            {
                "id": 2,
                "a": "https://via.placeholder.com/400x300/95E1D3/FFFFFF?text=Image+A2",
                "b": "https://via.placeholder.com/400x300/F38BA8/FFFFFF?text=Image+B2",
                "diff": "第二组图片比对分析显示了两张不同风格的占位符图像。图片A采用了薄荷绿色调，而图片B使用了粉红色调。详细分析如下：\n\n1. 色彩对比：A图使用清新的薄荷绿(#95E1D3)，给人以宁静、自然的感觉；B图使用温暖的粉红色(#F38BA8)，营造出温馨、活泼的氛围\n2. 视觉冲击：两种颜色形成强烈的冷暖对比\n3. 应用场景：A图更适合健康、环保类应用，B图更适合时尚、美妆类应用"
            },
            {
                "id": 3,
                "a": "https://via.placeholder.com/400x300/A8E6CF/FFFFFF?text=Image+A3",
                "b": "https://via.placeholder.com/400x300/FFD93D/FFFFFF?text=Image+B3",
                "diff": "第三组图片展示了绿色与黄色的对比效果。这两种颜色都属于暖色调，但在视觉表现上有显著差异：\n\n1. 颜色属性：A图的浅绿色(#A8E6CF)给人以生机勃勃的感觉，B图的明黄色(#FFD93D)则显得更加明亮和引人注目\n2. 心理效应：绿色通常与自然、成长、和谐相关联，而黄色则与快乐、创造力、警示相关\n3. 设计应用：绿色更适合表达环保、健康主题，黄色更适合表达活力、创新主题\n4. 可读性：两种颜色在白色文字的衬托下都具有良好的可读性"
            }
        ]
        save_data(sample_data)
        print(f"已创建示例数据文件: {DATA_FILE}")
    
    print("图片比对数据浏览系统启动中...")
    print("访问地址: http://localhost:5000")
    app.run(debug=False, host='::', port=9008)