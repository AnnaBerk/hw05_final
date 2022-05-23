import shutil
import tempfile

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import cache

from ..models import Post, Group

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)

User = get_user_model()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='author')
        cls.grouppag = Group.objects.create(
            title='grouppag',
            description='Тестовое описание',
            slug='slugpag',
        )
        cls.grouppag2 = Group.objects.create(
            title='grouppag2',
            description='Тестовое описание2',
            slug='slugpag2',
        )
        POSTGR1 = 13
        POSTGR2 = 5
        Post.objects.bulk_create(
            [Post(
                author=cls.user,
                text='Тестовый пост',
                group=cls.grouppag,) for _ in range(0, POSTGR1)]
        )
        Post.objects.bulk_create(
            [Post(
                author=cls.user,
                text='Тестовый пост',
                group=cls.grouppag2,) for _ in range(0, POSTGR2)]
        )

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def test_paginator(self):
        TEN_POSTS = 10
        EIGHT_POSTS = 8
        FIVE_POSTS = 5
        urls_posts = {
            '/': TEN_POSTS,
            '/?page=2': EIGHT_POSTS,
            '/group/slugpag/': TEN_POSTS,
            '/group/slugpag2/': FIVE_POSTS,
            '/profile/author/': TEN_POSTS,
            '/profile/author/?page=2': EIGHT_POSTS,
        }
        for url, cnt in urls_posts.items():
            with self.subTest(cnt=cnt):
                response = self.client.get(url)
                self.assertEqual(len(response.context['page_obj']), cnt)
