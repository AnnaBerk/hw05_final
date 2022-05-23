import shutil
import tempfile

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.urls import reverse
from django import forms
from django.core.cache import cache

from ..models import Post, Group, Follow

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)

User = get_user_model()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class GroupViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        cls.uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif',
        )
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='group',
            description='Тестовое описание',
            slug='slug',
        )
        cls.group2 = Group.objects.create(
            title='group2',
            description='Тестовое описание2',
            slug='slug2',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост больше 15 символов',
            group=cls.group,
            image=cls.uploaded,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    def response_authorized_post(self, name, data=None,
                                 resp_args=None, followed=True):
        return self.authorized_client.post(
            reverse(
                name,
                kwargs=resp_args
            ),
            data,
            follow=followed
        )

    def response_authorized_get(self, name, data=None,
                                resp_args=None, followed=True):
        return self.authorized_client.get(
            reverse(
                name,
                kwargs=resp_args
            ),
            data,
            follow=followed
        )

    def test_group_list_page_show_correct_context(self):
        """Пост group2 не попал на страницу записей group."""
        response = self.response_authorized_get(
            self, name='posts:group_list',
            resp_args={'slug': 'slug'}
        )
        first_object = response.context['page_obj'][0]
        post_group_0 = first_object.group.title
        self.assertNotEqual(post_group_0, 'group2')

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_list', kwargs={'slug': 'slug'}): (
                'posts/group_list.html'
            ),
            reverse('posts:profile', kwargs={'username': 'auth'}): (
                'posts/profile.html'
            ),
            reverse('posts:post_detail', kwargs={'post_id': '1'}): (
                'posts/post_detail.html'
            ),
            reverse('posts:post_create'): 'posts/create_post.html',
            reverse('posts:post_edit', kwargs={'post_id': '1'}): (
                'posts/create_post.html'
            ),
        }
        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def get_object(self, response,):
        res = response.context
        if 'page_obj' not in res:
            return response.context['post']
        return response.context['page_obj'][0]

    def test_context(func):
        def wrapper(self):
            response = func(self)
            object1 = self.get_object(response)
            contexts = {
                object1.author.username: self.post.author.username,
                object1.text: self.post.text,
                object1.group.title: self.post.group.title,
                object1.image: self.post.image,
            }
            for obj_ctx, self_ctx in contexts.items():
                with self.subTest():
                    self.assertEqual(obj_ctx, self_ctx)
        return wrapper

    @test_context
    def test_index_page_show_correct_context(self):
        """Шаблон index сформирован с правильным контекстом."""
        return self.guest_client.get(reverse('posts:index'))

    @test_context
    def test_group_list_page_show_correct_context(self):
        """Шаблон group_list сформирован с правильным контекстом."""
        return self.guest_client.get(reverse(
            'posts:group_list', kwargs={'slug': 'slug'})
        )

    @test_context
    def test_post_detail_page_show_correct_context(self):
        """Шаблон post_detail сформирован с правильным контекстом."""
        return self.guest_client.get(reverse(
            'posts:post_detail', kwargs={'post_id': '1'}
        ))

    def test_post_create_and_edit_page_show_correct_context(self):
        """Шаблон post_create и edit сформированы с правильным контекстом."""
        response_create_pg = self.response_authorized_get(
            name='posts:post_create'
        )
        response_edit_pg = self.response_authorized_get(
            name='posts:post_edit',
            resp_args={'post_id': '1'}
        )
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response_create_pg.context.get(
                    'form').fields.get(value)
                self.assertIsInstance(form_field, expected)
                form_field = response_edit_pg.context.get(
                    'form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_new_group_has_no_posts(self):
        """В новой группе не было постов"""
        form_data = {
            'text': 'Текст из формы',
            'group.title': 'newgroup',
        }
        self.response_authorized_post(
            name='posts:post_create',
            data=form_data,
        )

        post_cnt = self.group.posts_group.all().count()
        self.assertEqual(post_cnt, 1)

    def test_auth_follow(self):
        """ Авторизованный пользователь может подписываться на других
            пользователей и удалять их из подписок.
        """
        following = User.objects.create(username='following')
        self.response_authorized_post(
            name='posts:profile_follow',
            resp_args={'username': following}
        )
        self.assertIs(
            Follow.objects.filter(user=self.user, author=following).exists(),
            True
        )
        self.response_authorized_post(
            name='posts:profile_unfollow',
            resp_args={'username': following}
        )
        self.assertIs(
            Follow.objects.filter(user=self.user, author=following).exists(),
            False
        )

    def test_new_post(self):
        """ Новая запись пользователя появляется в ленте тех, кто на него
            подписан и не появляется в ленте тех, кто не подписан на него.
        """
        following = User.objects.create(username='following')
        Follow.objects.create(user=self.user, author=following)
        post = Post.objects.create(author=following, text="новый пост")

        response = self.response_authorized_get(
            name='posts:profile_follow',
            resp_args={'username': following}
        )

        self.assertIn(post.text, response.content.decode())
        response = self.guest_client.get(
            reverse('posts:profile_follow', kwargs={'username': following}),
            follow=True,
        )
        self.assertNotIn(post.text, response.content.decode())
