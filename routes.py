from utils import log
from models.user import User
from models.session import Session

import random


def template(name):
    """
    根据名字读取 templates 文件夹里的一个文件并返回
    """
    path = 'templates/' + name
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def current_user(request):
    session_id = request.cookies.get('session_id', '')
    if session_id is not None:
        s = Session.find_by(session_id=session_id)
        if s is None or s.expired():
            return User.guest()
        else:
            user_id = s.user_id
            u = User.find_by(id=user_id)
            return u
    return User.guest()


def random_string():
    """
    生成一个随机的字符串
    """
    seed = 'adfasdgkdfkasdjfnjsefjsdjf'
    s = ''
    for i in range(16):
        # 这里 len(seed) - 2 是因为我懒得去翻文档来确定边界了
        random_index = random.randint(0, len(seed) - 2)
        s += seed[random_index]
    return s


def response_with_headers(headers, code='233'):
    """
    header 包含 响应行 + headers
    Content-Type: text/html
    Set-Cookie: session_id=xxxxxxxx
    """
    header = 'HTTP/1.x {} SUPER OK\r\n'.format(code)
    header += ''.join([
        '{}: {}\r\n'.format(k, v) for k, v in headers.items()
    ])
    return header


def route_index(request):
    """
    主页的处理函数, 返回主页的响应
    """
    u = current_user(request)
    header = 'HTTP/1.1 233 SUPER OK\r\nContent-Type: text/html\r\n'
    body = template('index.html')
    body = body.replace('{{username}}', u.username)
    r = header + '\r\n' + body
    return r.encode()


def route_login(request):
    headers = {
        'Content-Type': 'text/html',
    }
    log('login, headers', request.headers)
    log('login, cookies', request.cookies)
    u = current_user(request)
    if request.method == 'POST':
        form = request.form()
        user_login = User.login_user(form)
        if user_login is not None:
            # 把 session-id 存入 cookie 中
            # 设置一个随机字符串来当 session_id 使用
            # 先用一个全局变量的字典 session 保存 session_id 和 username 的对应关系
            session_id = random_string()
            form = dict(
                session_id=session_id,
                user_id=user_login.id,
            )
            s = Session.new(form)
            s.save()
            # 在 header 中添加 Set-Cookie 字段
            # 告诉浏览器 下次访问的时候 带上 这个 cookie 服务器会验证其身份
            headers['Set-Cookie'] = 'session_id={}'.format(session_id)
            headers['location'] = '/'
            header = response_with_headers(headers, '302')
            return header.encode()
        else:
            result = '用户名或者密码错误'
    else:
        result = ''
    body = template('login.html')
    body = body.replace('{{result}}', result)
    body = body.replace('{{username}}', u.username)
    # 1. 写入 headers
    # 2. 包装成 header
    # 3. format header, body
    header = response_with_headers(headers)
    r = '{}\r\n{}'.format(header, body)
    log('login 的响应', r)
    return r.encode()


def route_register(request):
    if request.method == 'POST':
        form = request.form()
        u = User.new(form)
        if u.validate_register():
            u.save()
            result = '注册成功<br> <pre>{}</pre>'.format(User.all())
        else:
            result = '用户名或密码长度必须大于2'
    else:
        result = ''
    body = template('register.html')
    body = body.replace('{{result}}', result)
    header = 'HTTP/1.1 233 SUPER OK\r\nContent-Type: text/html\r\n'
    r = header + '\r\n' + body
    return r.encode()


def error(request, code=404):
    """
    根据 code 返回不同的错误响应
    目前只有 404
    """
    e = {
        404: b'HTTP/1.x 404 NOT FOUND\r\n\r\n<h1>NOT FOUND</h1>',
    }
    log('Error Page!! should return 404 not found')
    return e.get(code, b'')


def redirect(url):
    """
    给浏览器发送 302 跳转页面的响应
    在 HTTP header 里面添加 Location 字段并指定一个 url
    """
    headers = {
        'Location': url,
    }
    r = response_with_headers(headers, 302) + '\r\n'
    return r.encode()


def login_required(route_function):
    """
    装饰器
    用于登陆验证
    验证需要登陆的操作 在执行相应的路由函数之前执行
    """
    def f(request):
        u = current_user(request)
        if u.is_guest():
            log('游客用户')
            return redirect('/login')
        else:
            return route_function(request)

    return f


def users(request):
    """
    用户管理 页面
    只有 admin 可以访问
    """
    u = current_user(request)
    if u.is_admin():
        user_list = User.find_all()
        user_html = """
        <h3>
            id: {} username: {} password: {} 
        </h3>
        """
        user_html = ''.join([
            user_html.format(
                u.id, u.username, u.password,
            ) for u in user_list
        ])

        body = template('admin_users.html')
        body = body.replace('{{users}}', user_html)

        headers = {
            'Content-Type': 'text/html',
        }
        header = response_with_headers(headers)
        r = header + '\r\n' + body
        return r.encode()
    else:
        return redirect('/login')


def update(request):
    form = request.form()
    t = User.find_by(id=int(form['id']))
    u = current_user(request)
    if u.is_admin():
        User.update(form)
    else:
        return redirect('/login')

    return redirect('/admin/users')


def route_static(request):
    """
    静态资源的处理函数, 读取图片并生成响应返回
    """
    filename = request.query.get('file', 'doge.gif')
    path = 'static/' + filename
    with open(path, 'rb') as f:
        header = b'HTTP/1.x 233 SUPER OK\r\nContent-Type: image/gif\r\n\r\n'
        img = header + f.read()
        return img


def route_dict():
    d = {
        '/': route_index,
        '/login': route_login,
        '/register': route_register,
        '/admin/users': users,
        '/admin/users/update': update,
        '/static': route_static,
    }
    return d