from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/api/armstrong')
def armstrong():
    number = int(request.args.get('number', 0))
    if is_armstrong(number):
        return jsonify(message=f"{number} is an Armstrong number.")
    else:
        return jsonify(message=f"{number} is not an Armstrong number.")

def is_armstrong(number):
    order = len(str(number))
    sum = 0
    temp = number
    while temp > 0:
        digit = temp % 10
        sum += digit ** order
        temp //= 10
    return number == sum

if __name__ == '__main__':
    app.run(debug=True)
