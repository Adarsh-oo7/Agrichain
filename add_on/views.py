from django.shortcuts import render

def farming_news(request):
    return render(request, 'blog/farming_news.html')