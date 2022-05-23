import shutil
import tempfile

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings
from django.core.cache import cache

from ..models import Post

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)

User = get_user_model()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class GroupCacheTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
        )

    def setUp(self):
        self.guest_client = Client()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def test_index_cache(self):
        """
        Проверяем что механизм кеша главной страницы работает
        """
        url = reverse('posts:index')
        response = self.guest_client.get(url)
        self.assertEqual(len(response.context['page_obj']), 1)
        post = Post.objects.get(id=1)
        post.delete()
        response = self.guest_client.get(url)
        self. assertIn(post.text, response.content.decode())
        cache.clear()
        response = self.guest_client.get(url)
        self.assertNotIn(post.text, response.content.decode())
