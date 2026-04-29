from sklearn.linear_model import LinearRegression

def train_model(df):
    df = df.select_dtypes(include="number")
    if df.shape[1] < 2:
        return None

    X = df.iloc[:, :-1]
    y = df.iloc[:, -1]

    model = LinearRegression()
    model.fit(X, y)

    return model