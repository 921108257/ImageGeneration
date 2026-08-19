import unittest

from app.schemas import validate_image_options, validate_size


class GptImage2ValidationTests(unittest.TestCase):
    def test_accepts_custom_multiple_of_16(self) -> None:
        self.assertEqual(validate_size("1536x864", "gpt-image-2"), "1536x864")

    def test_rejects_non_multiple_of_16(self) -> None:
        with self.assertRaisesRegex(ValueError, "16"):
            validate_size("1537x864", "gpt-image-2")

    def test_rejects_oversized_or_extreme_aspect_ratio(self) -> None:
        for size in ("4096x2048", "3840x1024"):
            with self.subTest(size=size), self.assertRaises(ValueError):
                validate_size(size, "gpt-image-2")

    def test_rejects_transparency_for_gpt_image_2(self) -> None:
        with self.assertRaisesRegex(ValueError, "不支持透明背景"):
            validate_image_options(
                model="gpt-image-2",
                prompt="icon",
                n=1,
                size="1024x1024",
                quality="high",
                background="transparent",
                output_format="png",
                output_compression=None,
                moderation="auto",
            )

    def test_rejects_png_compression(self) -> None:
        with self.assertRaisesRegex(ValueError, "jpeg 或 webp"):
            validate_image_options(
                model="gpt-image-2",
                prompt="icon",
                n=1,
                size="1024x1024",
                quality="high",
                background="opaque",
                output_format="png",
                output_compression=80,
                moderation="auto",
            )


if __name__ == "__main__":
    unittest.main()
