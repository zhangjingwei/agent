"""
高级数学计算器工具
"""

import re
import math
from typing import Union


def calculate(expression: str) -> Union[int, float, complex]:
    """
    高级数学计算器函数

    支持数学运算：基本运算(+-*/), 幂运算(**), 函数(sqrt, sin, cos, tan, log, ln, exp, abs, factorial), 常量(pi, e)

    Args:
        expression: 数学表达式字符串

    Returns:
        计算结果

    Raises:
        ValueError: 当表达式无效时
    """
    if not expression or not isinstance(expression, str):
        raise ValueError("Expression must be a non-empty string")

    # 移除所有空格
    expression = expression.replace(" ", "")

    # 高级安全检查：只允许安全的数学表达式
    # 首先检查是否有危险的模式
    dangerous_patterns = [
        r'__\w+__',  # 双下划线属性
        r'import|exec|eval|open|file|input',  # 危险关键字
        r'\b\w+\([^)]*\)\(',  # 嵌套函数调用（过于复杂）
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, expression):
            raise ValueError(f"Expression contains unsafe patterns")

    # 检查表达式复杂度（防止DOS攻击）
    # 1. 函数调用数量限制
    func_count = len(re.findall(r'\w+\s*\(', expression))
    if func_count > 10:
        raise ValueError("Expression too complex: too many function calls (max: 10)")

    # 2. 嵌套深度检查（防止栈溢出）
    max_nesting = 0
    current_nesting = 0
    for char in expression:
        if char == '(':
            current_nesting += 1
            max_nesting = max(max_nesting, current_nesting)
        elif char == ')':
            current_nesting -= 1
            if current_nesting < 0:  # 不匹配的括号
                raise ValueError("Invalid parentheses: unmatched closing parenthesis")

    if max_nesting > 5:
        raise ValueError("Expression too complex: nesting depth too deep (max: 5 levels)")

    if current_nesting != 0:  # 不匹配的括号
        raise ValueError("Invalid parentheses: unmatched opening parenthesis")

    # 3. 表达式长度限制
    if len(expression) > 200:
        raise ValueError("Expression too long: maximum 200 characters")

    # 3. 检查可能的资源耗尽模式
    # 大数字检查（防止内存溢出）
    large_numbers = re.findall(r'\b\d+\b', expression)  # 使用\b确保是独立的数字
    for num_str in large_numbers:
        try:
            num = int(num_str)
            if num > 10**6:  # 超过100万的数字
                raise ValueError(f"Number too large: {num} (max: 1,000,000)")
        except ValueError as e:
            if "Number too large" in str(e):
                raise  # 重新抛出我们的安全检查异常
            pass  # 不是有效数字，跳过

    # 4. 检查危险的数学模式
    if '**' in expression:
        # 检查指数运算的幂是否过大
        power_matches = re.findall(r'\*\*\s*(\d+)', expression)
        for power_str in power_matches:
            try:
                power = int(power_str)
                if power > 100:  # 指数超过100
                    raise ValueError(f"Exponent too large: {power} (max: 100)")
            except ValueError:
                pass

    # 5. 检查阶乘参数
    if 'factorial' in expression:
        factorial_matches = re.findall(r'factorial\s*\(\s*(\d+)', expression)
        for n_str in factorial_matches:
            try:
                n = int(n_str)
                if n > 20:  # 阶乘超过20会非常大
                    raise ValueError(f"Factorial argument too large: {n} (max: 20)")
            except ValueError:
                pass

    # 检查函数调用是否只包含安全的数学函数
    func_calls = re.findall(r'(\w+)\(', expression)
    safe_functions = {
        'sqrt', 'cos', 'sin', 'tan', 'exp', 'abs', 'factorial',
        'pi', 'e', 'log', 'ln'
    }

    for func in func_calls:
        if func not in safe_functions:
            raise ValueError(f"Unsafe function detected: {func}")

    # 检查字符是否只包含允许的字符
    # 允许：数字、运算符、括号、点、以及函数名中的字母
    allowed_chars = set('0123456789+-*/().abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
    if not all(c in allowed_chars for c in expression):
        raise ValueError("Expression contains invalid characters")

    try:
        # 创建安全的数学环境
        safe_dict = {
            "__builtins__": {},
            # 基本数学函数
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "exp": math.exp,
            "log": math.log10,  # log是常用对数（底10）
            "ln": math.log,     # ln是自然对数
            "abs": abs,
            "factorial": math.factorial,
            # 数学常量
            "pi": math.pi,
            "e": math.e,
        }

        # 使用eval进行计算（在严格受控环境中）
        result = eval(expression, safe_dict)

        # 检查结果类型
        if not isinstance(result, (int, float, complex)):
            raise ValueError("Expression did not evaluate to a number")

        # 检查结果大小（防止内存溢出）
        if isinstance(result, (int, float)):
            if abs(result) > 10**100:  # 结果过大
                raise ValueError("Result too large (max: 10^100)")
        elif isinstance(result, complex):
            if abs(result) > 10**100:
                raise ValueError("Complex result magnitude too large (max: 10^100)")

        # 对于复数结果，如果虚部为0则返回实数
        if isinstance(result, complex) and result.imag == 0:
            return result.real

        return result

    except ZeroDivisionError:
        raise ValueError("除数不能为零")
    except OverflowError:
        raise ValueError("计算结果过大或溢出")
    except RecursionError:
        raise ValueError("表达式过于复杂或存在递归")
    except MemoryError:
        raise ValueError("内存不足，无法完成计算")
    except Exception as e:
        raise ValueError(f"表达式计算失败: {str(e)}")
